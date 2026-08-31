#!/usr/bin/env python3
"""Find registered compounds whose formula contradicts their own name.

A compound registered from `propose_chemicals.py` carries the laboratory's name
and the chemistry PubChem holds for that CAS number. If the CAS is wrong, or
PubChem cross-references it oddly, the entry ends up describing a different
substance. On 2026-08-25 a real entry paired `Glycerol, 2-monohexadecanoate`
with `2-Methoxyaniline` — C7H9NO where a C19 glycerol ester belongs.

**Comparing the two *names* does not work.** `Monostearin` and
`Glycerol, 1-monooctadecanoate` are the same substance and share no words;
`2,4-Di-tert-butylphenol` and `Phenol, 2,4-di-tertiobutyl` likewise. Word
overlap flags those as suspicious and is worse than useless.

Chemistry is checkable. A name saying *hexadecanoate* claims a sixteen-carbon
chain; if the formula has seven carbons, the two disagree and no naming
convention explains it. That is what this looks for.

It decides nothing — it sorts, so somebody reviewing hundreds of entries meets
the doubtful ones first instead of hunting for them.

    .venv/bin/python scripts/audit_chemicals.py              # the suspicious ones
    .venv/bin/python scripts/audit_chemicals.py --all        # every entry, ranked
    .venv/bin/python scripts/audit_chemicals.py -o ids.txt   # ids for remove_chemicals.py
"""

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("AUTO_INIT_DB", "false")

from app.database import SessionLocal  # noqa: E402
from app.models import Chemical  # noqa: E402
from app.store import all_docs  # noqa: E402

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
    "N": ("amin", "amid", "amide", "carbam", "nitr", "azo", "azin", "azol",
          "pyrid", "imid", "indol", "anilin", "cyan", "urea", "piperid",
          "morphol", "triaz", "purin", "pyrrol", "quinol", "nitril", "oxim"),
    "Cl": ("chlor",),
    "Br": ("brom",),
    "F": ("fluor",),
    "I": ("iodo", "iodi"),
    "S": ("thio", "sulf", "sulph", "mercapt", "thia"),
    "P": ("phosph",),
    "Si": ("silan", "silox", "silic", "silyl"),
    "B": ("boro", "borat"),
}


def implied_carbons(name: str) -> tuple[int, str]:
    """The longest carbon chain the name claims, and the stem that claimed it."""
    lowered = (name or "").lower()
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="show every entry, not just doubtful")
    parser.add_argument("-o", "--out", help="write the flagged identifiers to a file")
    args = parser.parse_args()

    db = SessionLocal()
    rows = []
    skipped = 0
    for doc in all_docs(db, Chemical):
        # PubChem's own name for the compound, however the entry was created.
        # The identification job stores it as `pubchem_title`; a spreadsheet
        # upload keeps the whole row under `metadata`, so it arrives as
        # PUBCHEM_NAME there. Reading only the first left every uploaded
        # compound unaudited — which was exactly the set that had never been
        # reviewed.
        title = doc.get("pubchem_title") or (doc.get("metadata") or {}).get("PUBCHEM_NAME")

        # The carbon-count test needs only the name and the formula, so an entry
        # without a PubChem name is still worth checking.
        if not doc.get("molecular_formula"):
            skipped += 1
            continue

        try:
            weight = float(doc.get("molecular_weight") or 0)
        except (TypeError, ValueError):
            weight = 0.0
        name = doc.get("name") or ""
        claimed, stem = implied_carbons(name)
        actual = formula_carbons(doc.get("molecular_formula"))

        reasons = []
        # A cell naming two compounds ('X + Y') describes co-eluting peaks. The
        # registered chemistry belongs to one of them, so a chain named by the
        # other is not evidence of an error.
        combined = " + " in name
        # The strong signal: the name names a chain the formula cannot hold.
        if claimed and actual and actual < claimed and not combined:
            reasons.append(
                f"name says '{stem}…' ({claimed} carbons) but the formula has {actual}"
            )
        # The formula contains an element the name never mentions.
        stray = unexplained_heteroatoms(name, doc.get("molecular_formula"))
        if stray:
            reasons.append(
                f"formula has {', '.join(stray)} but nothing in the name accounts for it"
            )

        # Severity for sorting: how far short the formula falls.
        gap = (claimed - actual) if reasons and claimed and actual else 0
        rows.append((-gap, reasons, doc))

    rows.sort(key=lambda r: (r[0], not r[1]))
    flagged = [r for r in rows if r[1]]
    shown = rows if args.all else flagged

    print(f"{len(rows)} entries checked ({skipped} skipped for having no formula).")
    print(f"{len(flagged)} look{'s' if len(flagged) == 1 else ''} doubtful.\n")

    for _, reasons, doc in shown:
        mark = "  ??" if reasons else "  ok"
        print(f"{mark}  {doc['chemical_id']}")
        print(f"        yours   : {doc.get('name')}")
        pubchem = doc.get("pubchem_title") or (doc.get("metadata") or {}).get("PUBCHEM_NAME")
        print(f"        pubchem : {pubchem or '(none recorded)'}")
        print(f"        cas={doc.get('cas_number')}  formula={doc.get('molecular_formula')}"
              f"  mw={doc.get('molecular_weight')}")
        for reason in reasons:
            print(f"        -> {reason}")
        print()

    if args.out and flagged:
        Path(args.out).write_text("".join(f"{d['chemical_id']}\n" for _, _, d in flagged))
        print(f"{len(flagged)} identifiers written to {args.out}")
        print("Review them, delete the lines you want to KEEP, then:")
        print(f"  scripts/remove_chemicals.py --from-file {args.out} --apply")

    print(
        "\nThis flags contradictions it can measure, not everything that is wrong.\n"
        "An entry it passes may still be mismatched — a wrong CAS pointing at a\n"
        "compound of similar size will not show up here. Read the pairs."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
