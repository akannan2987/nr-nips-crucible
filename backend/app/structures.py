"""One derived structure per entry, and the checks that say which of them the
registry can vouch for (phase CR-12, step A; docs/09-structures.md).

A compound's *structure* is the drawing chemists think in: which atoms,
joined how. The sources give it as text in three forms — a MOL block, a
SMILES, an InChI — and none of them is checked against the formula and the
weight the same source carries. This module reads whatever the entry has,
in the order decided as S5 (the MOL block, then the SMILES the chemist
entered, then the InChI), and stores one derived structure *beside* the
laboratory's own fields, never over them:

    structure: {source, smiles, inchi, inchikey, formula, weight, exact_mass,
                atoms, bonds, rings, charge, fragments, [largest_fragment],
                [repaired], [unreadable], checks, findings, derived_at}

Everything under `structure` is computed by RDKit from the structure alone.
The one design rule holds: it is one more fact in the document, no column,
no migration, and `derive_registry` is the only writer.

Then the checks. They compare what the source *says* (its formula, its
weight, its InChI) with what its own structure *is*:

* the laboratory's formula is compared with the formula of the whole
  structure and with each of its fragments. A salt is written as several
  fragments (`[Ag+].[O-][N+](=O)[O-]`) while the laboratory records the
  parent's formula (`Ag`); comparing with the whole structure alone flagged
  938 entries of the real export, comparing with the fragments too leaves
  398, every one a genuine disagreement (lesson 43);
* the laboratory's weight is compared with the *average* molecular weight
  and with the *exact* (monoisotopic) mass, of the whole structure and of
  each fragment: 6,179 of 6,382 real weights are exact masses to the fourth
  decimal, 314 are averages;
* an InChI the source carries beside a MOL block or a SMILES is turned into
  its InChIKey and compared with the derived one: a different first block
  is a different skeleton, a different second block a difference in stereo
  or charge only.

Each disagreement is a *structure finding* on the entry, the fifth kind on
the attention page (`app.audit`), with the same review mark as the others.
A SMILES the source wrapped in square brackets (`[CCO]`, 135 of the real
export) is read after removing them and the repair is recorded, not flagged.

Called by the endpoint (`POST /api/chemicals/structures/derive`), the
script (`derive_structures.py`) and the attention page's button, so the
three cannot disagree.
"""
from __future__ import annotations

import re
import time
from collections.abc import Callable
from typing import Any

from rdkit import Chem, RDLogger
from rdkit.Chem import Descriptors, rdMolDescriptors
from sqlalchemy.orm import Session

from .compat import now_iso
from .models import Chemical
from .store import all_rows, find_row, replace_doc

RDLogger.DisableLog("rdApp.*")

KEY_STRUCTURE = "structure"                 # the document key, and the review key on the attention page
SOURCE_ORDER = ("mol_block", "smiles", "inchi")   # decision S5
SOURCE_LABEL = {"mol_block": "MOL block", "smiles": "SMILES", "inchi": "InChI"}
FINDING_KINDS = ("formula", "weight", "inchi", "unreadable")
BATCH = 500                                 # rows per commit when applying
WEIGHT_TOLERANCE_ABS = 1.0                  # g/mol: a rounding, a hydrogen's worth of doubt
WEIGHT_TOLERANCE_REL = 0.005                # half a percent


# ------------------------------------------------------------- reading --

def source_fields(doc: dict[str, Any]) -> dict[str, str]:
    """The structure sources an entry carries, by name, in the order they are tried."""
    out: dict[str, str] = {}
    if doc.get("mol_block"):
        out["mol_block"] = str(doc["mol_block"])
    if doc.get("smiles"):
        out["smiles"] = str(doc["smiles"]).strip()
    inchi = doc.get("inchi") or doc.get("inchi_string")
    if inchi:
        out["inchi"] = str(inchi).strip()
    return out


def has_source(doc: dict[str, Any]) -> bool:
    return bool(source_fields(doc))


def _read_smiles(text: str) -> tuple[Chem.Mol | None, str | None]:
    """A SMILES, or the same after removing outer brackets the source added ('[CCO]')."""
    mol = Chem.MolFromSmiles(text)
    if mol is not None:
        return mol, None
    if len(text) > 2 and text.startswith("[") and text.endswith("]"):
        mol = Chem.MolFromSmiles(text[1:-1])
        if mol is not None:
            return mol, "outer brackets removed"
    return None, None


def read_structure(doc: dict[str, Any]) -> tuple[Chem.Mol | None, str | None, str | None, list[str]]:
    """The molecule, which source gave it, any repair, and the sources tried first that could not be read."""
    sources = source_fields(doc)
    unreadable: list[str] = []
    for name in SOURCE_ORDER:
        text = sources.get(name)
        if not text:
            continue
        repair = None
        if name == "mol_block":
            mol = Chem.MolFromMolBlock(text)
        elif name == "smiles":
            mol, repair = _read_smiles(text)
        else:
            mol = Chem.MolFromInchi(text)
        if mol is not None:
            return mol, name, repair, unreadable
        unreadable.append(name)
    return None, None, None, unreadable


# ------------------------------------------------------------ describing --

def normalise_formula(formula: Any) -> str:
    """Spaces and a trailing charge removed: 'C8 H10 N4 O2' and 'NO3-' compare by their atoms."""
    text = re.sub(r"\s+", "", str(formula or ""))
    return re.sub(r"[+-]\d*$", "", text)     # RDKit writes a charge as a trailing sign and count: 'C2H3O2-', 'O3Si-2'


def _facts(mol: Chem.Mol) -> dict[str, Any]:
    return {
        "formula": rdMolDescriptors.CalcMolFormula(mol),
        "weight": round(Descriptors.MolWt(mol), 3),
        "exact_mass": round(Descriptors.ExactMolWt(mol), 4),
        "atoms": mol.GetNumHeavyAtoms(),
    }


def describe(mol: Chem.Mol) -> tuple[dict[str, Any], list[Chem.Mol]]:
    """Everything computed from the structure alone, and its fragments."""
    frags = list(Chem.GetMolFrags(mol, asMols=True))
    out: dict[str, Any] = {
        "smiles": Chem.MolToSmiles(mol),
        "inchi": Chem.MolToInchi(mol),
        "inchikey": Chem.MolToInchiKey(mol),
        **_facts(mol),
        "bonds": mol.GetNumBonds(),
        "rings": rdMolDescriptors.CalcNumRings(mol),
        "charge": Chem.GetFormalCharge(mol),
        "fragments": len(frags),
    }
    if len(frags) > 1:
        # the biggest by heavy atoms, then by weight: in a hydrated salt of single atoms, the heaviest atom, not a water
        out["largest_fragment"] = _facts(max(frags, key=lambda m: (m.GetNumHeavyAtoms(), Descriptors.MolWt(m))))
    return out, frags


# -------------------------------------------------------------- checking --

def check(doc: dict[str, Any], mol: Chem.Mol, facts: dict[str, Any], frags: list[Chem.Mol], source: str) -> tuple[dict[str, str], list[dict[str, str]]]:
    """What the source says against what its structure is: a verdict per check, and the findings."""
    checks: dict[str, str] = {}
    findings: list[dict[str, str]] = []
    parts = [mol] + (frags if len(frags) > 1 else [])

    lab_formula = doc.get("molecular_formula")
    if lab_formula:
        candidates = {normalise_formula(rdMolDescriptors.CalcMolFormula(m)) for m in parts}
        if normalise_formula(lab_formula) in candidates:
            checks["formula"] = "agrees"
        else:
            checks["formula"] = "differs"
            where = f"the structure ({facts['formula']})" if len(frags) == 1 else f"the structure ({facts['formula']}) or any of its {len(frags)} fragments"
            findings.append({"kind": "formula", "reason": f"the laboratory's formula {lab_formula} is not the formula of {where}"})
    else:
        checks["formula"] = "none"

    lab_weight = doc.get("molecular_weight")
    if isinstance(lab_weight, (int, float)) and not isinstance(lab_weight, bool) and lab_weight > 0:
        nearest = min(abs(lab_weight - w) for m in parts for w in (Descriptors.MolWt(m), Descriptors.ExactMolWt(m)))
        if nearest <= max(WEIGHT_TOLERANCE_ABS, WEIGHT_TOLERANCE_REL * float(lab_weight)):
            checks["weight"] = "agrees"
        else:
            checks["weight"] = "differs"
            findings.append({"kind": "weight", "reason": f"the laboratory's weight {lab_weight} is neither the average weight ({facts['weight']}) nor the exact mass ({facts['exact_mass']}) of the structure or of a fragment"})
    else:
        checks["weight"] = "none"

    source_inchi = doc.get("inchi") or doc.get("inchi_string")
    if not source_inchi:
        checks["inchi"] = "none"
    elif source == "inchi":
        checks["inchi"] = "same source"
    elif not facts.get("inchikey"):
        # a polymer or a structure with placeholder atoms: RDKit makes no InChI for it, so there is nothing to compare with
        checks["inchi"] = "not computable"
        findings.append({"kind": "inchi", "reason": "the structure's own InChI could not be computed (placeholder atoms or a polymer), so the InChI the source carries could not be compared"})
    else:
        other = Chem.MolFromInchi(str(source_inchi).strip())
        if other is None:
            checks["inchi"] = "unreadable"
            findings.append({"kind": "inchi", "reason": "the InChI the source carries could not be read, so it could not be compared"})
        else:
            key_other, key_mine = Chem.MolToInchiKey(other), facts["inchikey"]
            if key_other == key_mine:
                checks["inchi"] = "agrees"
            elif key_other[:14] != key_mine[:14]:
                checks["inchi"] = "differs"
                findings.append({"kind": "inchi", "reason": f"the InChI the source carries describes a different skeleton (its key starts {key_other[:14]}, the structure's {key_mine[:14]})"})
            else:
                checks["inchi"] = "differs"
                findings.append({"kind": "inchi", "reason": "the InChI the source carries differs from the structure in the stereo or charge layer only"})
    return checks, findings


# --------------------------------------------------------------- derive --

def derive_one(doc: dict[str, Any]) -> dict[str, Any] | None:
    """The `structure` for one entry; None when the entry carries no structure source at all."""
    if not has_source(doc):
        return None
    mol, source, repair, unreadable = read_structure(doc)
    stamp = now_iso()
    if mol is None:
        return {
            "source": None,
            "unreadable": unreadable,
            "checks": {},
            "findings": [{"kind": "unreadable", "reason": "no structure could be read from the " + " or the ".join(SOURCE_LABEL[u] for u in unreadable) + " the source carries"}],
            "derived_at": stamp,
        }
    facts, frags = describe(mol)
    structure: dict[str, Any] = {"source": source, **facts}
    if repair:
        structure["repaired"] = repair
    if unreadable:
        structure["unreadable"] = unreadable
    structure["checks"], structure["findings"] = check(doc, mol, facts, frags, source)
    structure["derived_at"] = stamp
    return structure


def _same(a: dict[str, Any] | None, b: dict[str, Any]) -> bool:
    """Equal apart from the timestamp, so a re-run rewrites nothing."""
    if not a:
        return False
    strip = lambda s: {k: v for k, v in s.items() if k != "derived_at"}  # noqa: E731
    return strip(a) == strip(b)


def _item(doc: dict[str, Any], structure: dict[str, Any]) -> dict[str, Any]:
    """One line of the report: the laboratory's values beside the derived ones."""
    return {
        "chemical_id": doc.get("chemical_id"),
        "name": doc.get("name"),
        "molecular_formula": doc.get("molecular_formula"),
        "molecular_weight": doc.get("molecular_weight"),
        "source": structure.get("source"),
        "repaired": structure.get("repaired"),
        "formula": structure.get("formula"),
        "weight": structure.get("weight"),
        "exact_mass": structure.get("exact_mass"),
        "inchikey": structure.get("inchikey"),
        "fragments": structure.get("fragments"),
        "findings": [f["reason"] for f in structure.get("findings") or []],
        "kinds": sorted({f["kind"] for f in structure.get("findings") or []}),
    }


def derive_registry(db: Session, chemical_ids: list[str] | None = None, apply: bool = False,
                    progress: Callable[[int], None] | None = None) -> dict[str, Any]:
    """Derive for every entry, or for the identifiers given; report, and write only on `apply`.

    The report counts where each structure came from, what could not be
    read, and the findings by kind, and lists every entry with a finding.
    With `apply` the `structure` is written on each entry (a re-run that
    changes nothing writes nothing); the entry's `updated_at` is left alone,
    because a derived fact is not an edit of the record. Raises KeyError
    naming the first unknown identifier, so nothing is written for a bad list.
    """
    if chemical_ids:
        rows = []
        for chemical_id in chemical_ids:
            row = find_row(db, Chemical, "chemical_id", chemical_id)
            if row is None:
                raise KeyError(chemical_id)
            rows.append(row)
    else:
        rows = all_rows(db, Chemical)

    started = time.monotonic()
    report: dict[str, Any] = {
        "entries": len(rows),
        "with_source": 0,
        "derived": 0,
        "from": {name: 0 for name in SOURCE_ORDER},
        "repaired": 0,
        "unreadable": 0,
        "findings": {"entries": 0, **{kind: 0 for kind in FINDING_KINDS}},
        "applied": bool(apply),
        "written": 0,
        "unchanged": 0,
        "items": [],
    }
    for i, row in enumerate(rows, start=1):
        doc = row.doc or {}
        structure = derive_one(doc)
        if structure is None:
            continue
        report["with_source"] += 1
        if structure["source"]:
            report["derived"] += 1
            report["from"][structure["source"]] += 1
            if structure.get("repaired"):
                report["repaired"] += 1
        else:
            report["unreadable"] += 1
        findings = structure.get("findings") or []
        if findings:
            report["findings"]["entries"] += 1
            for kind in {f["kind"] for f in findings}:
                report["findings"][kind] += 1
            report["items"].append(_item(doc, structure))
        if apply:
            if _same(doc.get(KEY_STRUCTURE), structure):
                report["unchanged"] += 1
            else:
                new_doc = dict(doc)
                new_doc[KEY_STRUCTURE] = structure
                replace_doc(db, row, new_doc, commit=False)
                report["written"] += 1
                if report["written"] % BATCH == 0:
                    db.commit()
        if progress and i % 1000 == 0:
            progress(i)
    if apply:
        db.commit()
    report["seconds"] = round(time.monotonic() - started, 1)
    return report


def structures_summary(docs: list[dict[str, Any]]) -> dict[str, int]:
    """How far the registry is: entries with a source, derived, still to derive, with findings. No RDKit."""
    with_source = derived = findings = 0
    for doc in docs:
        structure = doc.get(KEY_STRUCTURE)
        if structure is None:
            if has_source(doc):
                with_source += 1
            continue
        with_source += 1
        if structure.get("source"):
            derived += 1
        if structure.get("findings"):
            findings += 1
    return {"with_source": with_source, "derived": derived, "to_derive": with_source - derived - sum(1 for d in docs if d.get(KEY_STRUCTURE) and not d[KEY_STRUCTURE].get("source")), "findings": findings}
