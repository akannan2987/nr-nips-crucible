"""What in the registry needs a person's eye, and the marks a person leaves.

One home for the registry audit, called by both the endpoint
(`GET /api/chemicals/audit`) and the terminal script (`audit_chemicals.py`),
so the browser and the terminal cannot disagree about what is flagged
(the rule recorded in the roadmap on 2026-09-09: anything a maintenance
script can do, the browser must be able to do too).

Four kinds of thing are listed:

* **shared identifiers** — two or more entries carry the same CAS number,
  DTXSID or PubChem compound id. Derived from the data, not from the flags
  the import set, so an entry created by any route is seen, and an entry
  that was merged away stops appearing;
* **batch conflicts** — a compound whose batch rows disagree on a column,
  each batch's own value beside the others;
* **pending identifiers** — entries from the limited list still waiting
  for their identifier;
* **formula findings** — the chemistry checks that have lived in the audit
  script since phase 04: a name claiming a chain the formula cannot hold, an
  element in the formula nothing in the name accounts for.

A person **reviews** an item by leaving a mark on the entry:
``doc["reviewed"] = {"<key>": "<timestamp>"}``, where the key names what was
looked at (``shared:cas:58-08-2``, ``batch_conflicts``, ``formula``). A
reviewed item stays listed, greyed, and no longer counts on the banner. The
mark is data in the document, like every other fact about an entry.

**Comparing the two *names* does not work.** `Monostearin` and
`Glycerol, 1-monooctadecanoate` are the same substance and share no words;
`2,4-Di-tert-butylphenol` and `Phenol, 2,4-di-tertiobutyl` likewise. Word
overlap flags those as suspicious and is worse than useless. Chemistry is
checkable: a name saying *hexadecanoate* claims a sixteen-carbon chain; if
the formula has seven carbons, the two disagree and no naming convention
explains it. That is what the formula check looks for. It decides nothing —
it sorts, so somebody reviewing hundreds of entries meets the doubtful ones
first instead of hunting for them.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from .compat import now_iso
from .links import link_counts
from .models import Chemical
from .store import all_rows, find_row, replace_doc

# ------------------------------------------------------------ chemistry --

# Chain-length stems and the carbons each implies. These are the standard
# multipliers in organic nomenclature: a name containing 'hexadec' claims a
# sixteen-carbon chain, whatever else it says.
CHAIN_CARBONS = {
    "octacos": 28, "hexacos": 26, "tetracos": 24, "docos": 22, "eicos": 20,
    "octadec": 18, "heptadec": 17, "hexadec": 16, "pentadec": 15, "tetradec": 14,
    "tridec": 13, "dodec": 12, "undec": 11, "decan": 10, "nonan": 9, "octan": 8,
}

# Elements beyond carbon, hydrogen and oxygen, and the name fragments that
# earn them. An ester, a diol or a benzoate is built from C, H and O; if the
# formula also contains nitrogen or chlorine, the name has to say so somewhere.
# This is the strongest signal available: on real data every mismatched entry
# whose formula carried an unexplained heteroatom was genuinely the wrong
# compound.
HETEROATOMS = {
    "N": ("amin", "amid", "amide", "anilid", "carbam", "lactam", "nitr", "azo",
          "azin", "azol", "pyrid", "imid", "imin", "indol", "anilin", "cyan",
          "urea", "piperid", "morphol", "triaz", "purin", "pyrrol", "quinol",
          "nitril", "oxim", "thiazol", "isothiazol"),
    "Cl": ("chlor",),
    "Br": ("brom",),
    "F": ("fluor",),
    "I": ("iodo", "iodi"),
    "S": ("thio", "sulf", "sulph", "mercapt", "thia"),
    "P": ("phosph",),
    "Si": ("silan", "silox", "silic", "silyl"),
    "B": ("boro", "borat"),
}


# A multiplier glued to a halogen counts that halogen, not carbons:
# 'tridecafluorohexyl' is thirteen fluorines on a six-carbon chain. Such words
# are removed before the chain stems are looked for. (Found on the real export:
# 37 chain findings, most of them perfluorinated surfactants named this way.)
_HALOGEN_MULTIPLIER = re.compile(r"[a-z]*(fluoro|chloro|bromo|iodo)")


def implied_carbons(name: str) -> tuple[int, str]:
    """The longest carbon chain the name claims, and the stem that claimed it."""
    lowered = _HALOGEN_MULTIPLIER.sub(" ", (name or "").lower())
    best, source = 0, ""
    for stem, count in CHAIN_CARBONS.items():
        if stem in lowered and count > best:
            best, source = count, stem
    return best, source


def formula_carbons(formula: str) -> int:
    """Carbon count from a molecular formula; 0 when it cannot be read."""
    match = re.match(r"^C(\d*)(?![a-z])", (formula or "").strip())
    if not match:
        return 0
    return int(match.group(1)) if match.group(1) else 1


def formula_elements(formula: str) -> set[str]:
    """Every element symbol in a molecular formula."""
    return set(re.findall(r"[A-Z][a-z]?", formula or ""))


def _same_name(a: str, b: str) -> bool:
    """Whether two chemical names are the same once punctuation is ignored."""
    norm = lambda t: re.sub(r"[^a-z0-9]", "", (t or "").lower())  # noqa: E731
    return bool(norm(a)) and norm(a) == norm(b)


def unexplained_heteroatoms(name: str, formula: str) -> list[str]:
    """Elements in the formula that nothing in the name accounts for.

    Carbon, hydrogen and oxygen are assumed throughout — practically every
    organic name implies them. Anything else has to be earned by a fragment of
    the name: `chloro`, `amide`, `phosph`. A benzoate whose formula contains
    nitrogen is describing something the name does not.
    """
    lowered = (name or "").lower()
    found = []
    for element in formula_elements(formula) - {"C", "H", "O"}:
        hints = HETEROATOMS.get(element)
        if hints is None:
            continue  # an element we have no vocabulary for; say nothing
        if not any(hint in lowered for hint in hints):
            found.append(element)
    return sorted(found)


def evidence_text(doc: dict[str, Any]) -> str:
    """Every name the entry carries, joined: what the formula's elements can be checked against.

    A synonym is another name for the same substance, so a chlorine the
    trivial name never mentions (`DDT`) is accounted for by a synonym that
    does (`1,1'-(2,2,2-trichloroethylidene)bis(4-chlorobenzene)`). On the real
    export this took the heteroatom findings from 495 to under a third of
    that, every one removed being a name the entry itself explained.
    """
    parts: list[str] = [str(doc.get("name") or ""), str(doc.get("iupac_name") or ""), str(pubchem_name(doc) or "")]
    for key in ("synonyms", "other_names"):
        value = doc.get(key)
        if isinstance(value, list):
            parts.extend(str(v) for v in value if v)
        elif value:
            parts.append(str(value))
    return " ; ".join(parts)


def pubchem_name(doc: dict[str, Any]) -> str | None:
    """PubChem's own name for the compound, however the entry was created.

    The identification job stores it as `pubchem_title`; a spreadsheet upload
    keeps the whole row under `metadata`, so it arrives as PUBCHEM_NAME there.
    Reading only the first left every uploaded compound unaudited — which was
    exactly the set that had never been reviewed.
    """
    return doc.get("pubchem_title") or (doc.get("metadata") or {}).get("PUBCHEM_NAME")


def chemistry_findings(doc: dict[str, Any]) -> tuple[list[str], int]:
    """The reasons an entry's formula contradicts its own name, and a severity.

    Returns ``([], 0)`` for an entry that passes, or has no formula to check.
    The severity is how far short the formula falls of the chain the name
    claims; it only orders the list.
    """
    if not doc.get("molecular_formula"):
        return [], 0
    name = doc.get("name") or ""
    formula = doc.get("molecular_formula")
    claimed, stem = implied_carbons(name)
    actual = formula_carbons(formula)

    reasons: list[str] = []
    # A cell naming two compounds ('X + Y') describes co-eluting peaks. The
    # registered chemistry belongs to one of them, so a chain named by the
    # other is not evidence of an error.
    combined = " + " in name
    # The strong signal: the name names a chain the formula cannot hold.
    if claimed and actual and actual < claimed and not combined:
        reasons.append(f"name says '{stem}…' ({claimed} carbons) but the formula has {actual}")
    # When both names say the same thing there is no disagreement to
    # investigate, whatever the elements. A trivial name such as 'Caffeine'
    # carries no structural hint at all, so the vocabulary can never account
    # for its nitrogen — but PubChem agreeing with it is far better evidence
    # than any word list.
    title = pubchem_name(doc)
    agreed = bool(title and _same_name(name, title))
    stray = [] if agreed else unexplained_heteroatoms(evidence_text(doc), formula)
    if stray:
        reasons.append(f"formula has {', '.join(stray)} but nothing in the name accounts for it")

    # The weight was once part of an "ester implies heavy" heuristic that
    # produced 28 false alarms in 41 and was removed; only checkable
    # chemistry remains (lessons entry 26).
    gap = (claimed - actual) if reasons and claimed and actual else 0
    return reasons, gap


# ---------------------------------------------------------------- audit --

SHARED_KINDS = (("cas", "cas_number", "CAS number"), ("dtxsid", "dtx_id", "DTXSID"), ("pubchem", "pubchem_cid", "PubChem compound"))
KEY_BATCH = "batch_conflicts"
KEY_FORMULA = "formula"


def shared_key(kind: str, value: Any) -> str:
    """The review key of a shared-identifier group: ``shared:cas:58-08-2``."""
    return f"shared:{kind}:{value}"


def is_reviewed(doc: dict[str, Any], key: str) -> bool:
    return bool((doc.get("reviewed") or {}).get(key))


def _summary(doc: dict[str, Any], links: dict[str, int] | None) -> dict[str, Any]:
    """The fields the attention page shows for one entry, side by side with its neighbours."""
    out = {
        "chemical_id": doc.get("chemical_id"),
        "name": doc.get("name"),
        "cas_number": doc.get("cas_number"),
        "dtx_id": doc.get("dtx_id"),
        "pubchem_cid": doc.get("pubchem_cid"),
        "molecular_formula": doc.get("molecular_formula"),
        "molecular_weight": doc.get("molecular_weight"),
        "dotmatics_reg_id": doc.get("dotmatics_reg_id"),
        "source_template": doc.get("source_template"),
        "merged_from": doc.get("merged_from") or [],
        "batches": len(doc.get("batches") or []),
        "created_at": doc.get("created_at"),
    }
    if links is not None:
        out["linked_rows"] = links.get(doc.get("chemical_id") or "", 0)
    return out


def audit_registry(db: Session, with_links: bool = True, everything: bool = False) -> dict[str, Any]:
    """Everything a person should look at, grouped by kind, with the review marks.

    `with_links` adds each entry's count of linked measurement rows (the page
    shows it beside the merge choice; the banner's counts do not need it).
    `everything` also returns every entry the formula check passed, ranked —
    the script's ``--all``.
    """
    docs = [row.doc or {} for row in all_rows(db, Chemical)]
    links = link_counts(db) if with_links else None

    # shared identifiers, from the data
    shared: list[dict[str, Any]] = []
    for kind, field, _label in SHARED_KINDS:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for doc in docs:
            value = doc.get(field)
            if value not in (None, "", 0):
                groups[str(value).strip()].append(doc)
        for value, members in groups.items():
            if len(members) < 2:
                continue
            key = shared_key(kind, value)
            shared.append({
                "key": key,
                "kind": kind,
                "value": value,
                "reviewed": all(is_reviewed(d, key) for d in members),
                "entries": [_summary(d, links) for d in sorted(members, key=lambda d: d.get("chemical_id") or "")],
            })
    shared.sort(key=lambda g: (g["reviewed"], g["kind"], g["value"]))

    # batch conflicts, each batch's value of each disputed column
    conflicts: list[dict[str, Any]] = []
    for doc in docs:
        columns = doc.get("batch_conflicts") or []
        if not columns:
            continue
        batches = doc.get("batches") or []
        conflicts.append({
            **_summary(doc, links),
            "key": KEY_BATCH,
            "reviewed": is_reviewed(doc, KEY_BATCH),
            "columns": [
                {
                    "column": column,
                    "promoted": (doc.get("metadata") or {}).get(column),
                    "values": [
                        {"batch": i, "batch_id": b.get("BATCH_ID") or b.get("FORMATTED_BATCH_ID"), "value": b.get(column)}
                        for i, b in enumerate(batches, start=1)
                    ],
                }
                for column in columns
            ],
        })
    conflicts.sort(key=lambda c: (c["reviewed"], c["chemical_id"] or ""))

    # pending identifiers
    pending = [
        {**_summary(doc, links), "pending_from": doc.get("nestle_id_pending"), "supplier": doc.get("supplier")}
        for doc in docs
        if doc.get("nestle_id_pending")
    ]

    # formula findings
    formula: list[dict[str, Any]] = []
    passed: list[dict[str, Any]] = []
    checked = skipped = 0
    for doc in docs:
        if not doc.get("molecular_formula"):
            skipped += 1
            continue
        checked += 1
        reasons, gap = chemistry_findings(doc)
        item = {**_summary(doc, links), "pubchem_name": pubchem_name(doc), "reasons": reasons, "severity": gap}
        if reasons:
            formula.append({**item, "key": KEY_FORMULA, "reviewed": is_reviewed(doc, KEY_FORMULA)})
        elif everything:
            passed.append(item)
    formula.sort(key=lambda f: (f["reviewed"], -f["severity"], f["chemical_id"] or ""))

    open_shared = [g for g in shared if not g["reviewed"]]
    counts = {
        "shared_groups": len(open_shared),
        "shared_entries": len({e["chemical_id"] for g in open_shared for e in g["entries"]}),
        "batch_conflicts": sum(1 for c in conflicts if not c["reviewed"]),
        "pending": len(pending),
        "formula": sum(1 for f in formula if not f["reviewed"]),
        "reviewed": sum(1 for g in shared if g["reviewed"]) + sum(1 for c in conflicts if c["reviewed"]) + sum(1 for f in formula if f["reviewed"]),
    }
    counts["attention"] = counts["shared_groups"] + counts["batch_conflicts"] + counts["pending"] + counts["formula"]

    result = {
        "counts": counts,
        "checked": checked,
        "skipped": skipped,
        "shared": shared,
        "batch_conflicts": conflicts,
        "pending": pending,
        "formula": formula,
    }
    if everything:
        result["passed"] = passed
    return result


def registry_notices(db: Session) -> dict[str, int]:
    """What the Chemical Registry page keeps showing until someone acts.

    The three original counts keep their names (`cas_shared` counts entries in
    any open shared-identifier group, as it always did); `formula` and
    `attention` were added with the attention page.
    """
    counts = audit_registry(db, with_links=False)["counts"]
    return {
        "nestle_id_pending": counts["pending"],
        "cas_shared": counts["shared_entries"],
        "batch_conflicts": counts["batch_conflicts"],
        "formula": counts["formula"],
        "attention": counts["attention"],
    }


# --------------------------------------------------------------- review --

def mark_reviewed(db: Session, chemical_ids: list[str], key: str, reviewed: bool) -> int:
    """Leave (or lift) the review mark `key` on each entry; returns how many changed.

    Raises KeyError naming the first unknown identifier, so the caller can
    answer 404 — nothing is written when any id is unknown.
    """
    rows = []
    for chemical_id in chemical_ids:
        row = find_row(db, Chemical, "chemical_id", chemical_id)
        if row is None:
            raise KeyError(chemical_id)
        rows.append(row)
    changed = 0
    stamp = now_iso()
    for row in rows:
        doc = dict(row.doc or {})
        marks = dict(doc.get("reviewed") or {})
        if reviewed and not marks.get(key):
            marks[key] = stamp
        elif not reviewed and key in marks:
            marks.pop(key)
        else:
            continue
        if marks:
            doc["reviewed"] = marks
        else:
            doc.pop("reviewed", None)
        doc["updated_at"] = stamp
        replace_doc(db, row, doc, commit=False)
        changed += 1
    db.commit()
    return changed


def set_identifier(db: Session, chemical_id: str, nestle_id: str) -> dict[str, Any]:
    """Fill in a pending identifier by hand; the pending flag goes with it."""
    row = find_row(db, Chemical, "chemical_id", chemical_id)
    if row is None:
        raise KeyError(chemical_id)
    doc = dict(row.doc or {})
    doc["nestle_id"] = nestle_id
    doc.pop("nestle_id_pending", None)
    doc["updated_at"] = now_iso()
    replace_doc(db, row, doc)
    return doc
