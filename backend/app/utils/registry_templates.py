"""The real sources of registry entries, described as data (phase CR-9).

Phase 04 did this for screening exports: a laboratory file format is a
**template specification** — a fingerprint that recognises it, a map from
its columns to the application's fields, and the rule that everything else
is kept — not a parser written per file. The same idea for the Chemical
Registry, for the three real sources the laboratory has:

* the **Dotmatics export** (a spreadsheet, 115 columns, one row per *batch*
  of a compound, so several rows may describe one compound);
* the **registry SDF** (structures in V3000 form with ~50 regulatory and
  presence properties per molecule);
* the **limited list** (six columns; the identifier column says *Coming
  from screening*, which means: register now, fill the identifier in later
  from the screening data).

Every spec answers four questions: *how do I recognise this file?* *which
compound is a row about?* *which columns become the registry's own fields?*
*what happens to the rest?* — and the rest is always kept, under
``metadata``, because the document is the record.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# ------------------------------------------------------------------ helpers --

PENDING_SCREENING = re.compile(r"coming\s+from\s+screening", re.IGNORECASE)


def split_names(value: Any) -> list[str]:
    """A synonyms cell → a list. Semicolons and pipes separate; commas do not
    (they sit inside names: 'Phenol, 2,4-di-tert-butyl-')."""
    if value in (None, ""):
        return []
    parts = re.split(r"[;|\n]+", str(value))
    seen: list[str] = []
    for p in parts:
        p = p.strip()
        if p and p not in seen:
            seen.append(p)
    return seen


def as_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value).strip() or None


def as_number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def as_int_text(value: Any) -> str | None:
    """'12345.0' → '12345'; an identifier that arrived as a float."""
    t = as_text(value)
    if t is None:
        return None
    if re.fullmatch(r"\d+\.0+", t):
        return t.split(".")[0]
    return t


def first(row: dict[str, Any], *names: str) -> Any:
    for n in names:
        v = row.get(n)
        if v not in (None, ""):
            return v
    return None


# --------------------------------------------------------------------- spec --

@dataclass(frozen=True)
class RegistrySpec:
    """One source of registry entries, as data."""

    key: str
    label: str
    kind: str                       # "sheet" (csv/xlsx rows) or "sdf" (molecule properties)
    fingerprint: tuple[str, ...]    # header / property names that must all be present
    group_by: str | None            # column whose value identifies ONE compound (rows sharing it are batches)
    match_order: tuple[str, ...]    # registry fields to look an existing entry up by, in order
    promote: Callable[[dict[str, Any]], dict[str, Any]]   # row/properties → registry fields
    batch_fields: tuple[str, ...] = ()   # columns that legitimately differ per batch
    source: str = ""
    notes: str = ""
    exact: bool = False             # True: the file's columns must be EXACTLY the fingerprint, no more
    extra: dict[str, Any] = field(default_factory=dict)

    def matches(self, names: set[str]) -> bool:
        lowered = {n.strip().lower() for n in names if n}
        wanted = {f.lower() for f in self.fingerprint}
        return lowered == wanted if self.exact else wanted <= lowered


# ------------------------------------------------------------- Dotmatics --

DOTMATICS_BATCH_FIELDS = (
    "BATCH_ID", "BATCH_NUMBER", "FORMATTED_BATCH_ID",
    "GC_RI_METHOD", "GC_RI_METHOD_2", "RI_PACKAGING_L", "RI_COMPILATION",
    "RI_HS_NIST", "HS_RI_METHOD_1", "HS_RI_METHOD_2", "LC_RT_METHOD_1", "LC_RT_METHOD_2",
    "NESTLE_DEPT",
)


def _promote_dotmatics(row: dict[str, Any]) -> dict[str, Any]:
    """The registry's own fields from a Dotmatics row; everything stays in metadata."""
    pubchem = as_int_text(first(row, "PUBCHEM_ID"))
    fields: dict[str, Any] = {
        "dotmatics_reg_id": as_int_text(first(row, "REG_ID")),
        "name": as_text(first(row, "CHEMICAL_NAME")) or "Unknown",
        "cas_number": as_text(first(row, "CAS_NO")),
        "other_names": split_names(first(row, "OTHER_NAMES")),
        "synonyms": split_names(first(row, "SYNONYMS")),
        "dtx_id": as_text(first(row, "DTXSID")),
        "pubchem_cid": int(pubchem) if pubchem and pubchem.isdigit() else pubchem,
        "smiles": as_text(first(row, "SMILES_ORIGINAL", "SMILES_NEUT", "MOLECULE_CANON_SMILES")),
        "smiles_neutral": as_text(first(row, "SMILES_NEUT")),
        "inchi": as_text(first(row, "INCHI")),
        "molecular_formula": as_text(first(row, "MOL_FORMULA", "MOL_FORMULA_ORIG")),
        "molecular_weight": as_number(first(row, "MOL_WEIGHT_ORIG", "MW_NEUT", "MOL_WEIGHT_NEUT")),
        "xlogp": as_number(first(row, "XLOGP_ORIG", "XLOGP_NEUT")),
        "nestle_id": as_text(first(row, "NESTLE_ID")),
        "family": as_text(first(row, "FAMILY")),
        "type_origin": as_text(first(row, "TYPE_ORIGIN")),
        "vapor_pressure": as_number(first(row, "VAPOR_PRESSURE")),
        "source": "dotmatics",
    }
    return {k: v for k, v in fields.items() if v not in (None, "", [])}


DOTMATICS_EXPORT = RegistrySpec(
    key="dotmatics_export",
    label="Dotmatics registry export",
    kind="sheet",
    fingerprint=("REG_ID", "BATCH_ID", "FORMATTED_BATCH_ID", "CHEMICAL_NAME", "CAS_NO", "DTXSID"),
    group_by="REG_ID",
    match_order=("dotmatics_reg_id", "dtx_id"),
    promote=_promote_dotmatics,
    batch_fields=DOTMATICS_BATCH_FIELDS,
    source="dotmatics",
    notes=(
        "One row per batch; rows sharing REG_ID are one compound. Batch-level "
        "columns go to a `batches` list on the entry; a column outside that list "
        "that differs between a compound's batches is a `batch_conflicts` flag for "
        "the audit. Every column is kept under metadata."
    ),
)


# ------------------------------------------------------------------- SDF --

def _promote_registry_sdf(props: dict[str, Any]) -> dict[str, Any]:
    """The registry's own fields from a registry-SDF molecule's properties."""
    lc = {k.strip().lower(): v for k, v in props.items()}

    def get(*names: str) -> Any:
        for n in names:
            v = lc.get(n.lower())
            if v not in (None, ""):
                return v
        return None

    fields: dict[str, Any] = {
        "name": as_text(get("Chemical name", "PREFERRED_NAME")) or "Unknown",
        "preferred_name": as_text(get("PREFERRED_NAME")),
        "cas_number": as_text(get("CAS Number", "CAS_NO")),
        "dtx_id": as_text(get("DTXSID")),
        "synonyms": split_names(get("Synonyms / Composition")),
        "smiles": as_text(get("SMILES")),
        "ms_ready_smiles": as_text(get("MS_READY_SMILES")),
        "inchi": as_text(get("INCHI_STRING")),
        "molecular_formula": as_text(get("MOLECULAR_FORMULA", "Molecular Formula")),
        "molecular_weight": as_number(get("Exact Molecular Weight")),
        "monoisotopic_mass": as_number(get("MONOISOTOPIC_MASS")),
        "xlogp": as_number(get("log P(o/w) (25°C)", "log P(o/w) (25�C)")),
        "found_by": as_text(get("FOUND_BY")),
        "mol_block": props.get("_mol_block"),
        "structural": props.get("_structure"),
        "structure_warnings": props.get("_warnings") or None,
        "source": "registry_sdf",
    }
    return {k: v for k, v in fields.items() if v not in (None, "", [])}


REGISTRY_SDF = RegistrySpec(
    key="registry_sdf",
    label="Registry structure file (SDF, V3000)",
    kind="sdf",
    fingerprint=("DTXSID", "PREFERRED_NAME", "CAS Number", "Chemical name"),
    group_by=None,
    match_order=("dtx_id", "cas_number"),
    promote=_promote_registry_sdf,
    source="registry_sdf",
    notes=(
        "One molecule per compound. Merges with a Dotmatics entry on DTXSID: the "
        "export supplies the identifiers, the SDF supplies the structure. Every "
        "property is kept under metadata; the MOL block is kept and drawn."
    ),
)


# ---------------------------------------------------------- limited list --

def _promote_limited(row: dict[str, Any]) -> dict[str, Any]:
    nestle = as_text(first(row, "NESTLE_ID"))
    pending = bool(nestle and PENDING_SCREENING.search(nestle))
    fields: dict[str, Any] = {
        "name": as_text(first(row, "CHEMICAL_NAME")) or "Unknown",
        "cas_number": as_text(first(row, "CAS_NO")),
        "molecular_formula": as_text(first(row, "MOL_FORMULA")),
        "molecular_weight": as_number(first(row, "MOL_WEIGHT_ORIG")),
        "supplier": as_int_text(first(row, "Supplier_ref")),
        "nestle_id": None if pending else nestle,
        "nestle_id_pending": "screening" if pending else None,
        "source": "limited_list",
    }
    return {k: v for k, v in fields.items() if v not in (None, "", [])}


LIMITED_LIST = RegistrySpec(
    key="limited_list",
    label="Limited chemicals list (identifier to come from screening data)",
    kind="sheet",
    fingerprint=("Supplier_ref", "CAS_NO", "CHEMICAL_NAME", "MOL_WEIGHT_ORIG", "MOL_FORMULA", "NESTLE_ID"),
    group_by=None,
    match_order=("cas_number", "name"),
    promote=_promote_limited,
    source="limited_list",
    exact=True,  # the generic template carries these six columns too, plus DTX_ID; only the bare six are this list
    notes=(
        "NESTLE_ID = 'Coming from screening' means the identifier is not known yet: "
        "the entry is registered with `nestle_id_pending: screening` and the registry "
        "shows a notice until the NR screening data supplies it."
    ),
)


REGISTRY: tuple[RegistrySpec, ...] = (DOTMATICS_EXPORT, REGISTRY_SDF, LIMITED_LIST)


def detect_sheet_spec(headers: list[str]) -> RegistrySpec | None:
    names = {h for h in headers if h}
    for spec in REGISTRY:
        if spec.kind == "sheet" and spec.matches(names):
            return spec
    return None


def detect_sdf_spec(properties: dict[str, Any]) -> RegistrySpec | None:
    for spec in REGISTRY:
        if spec.kind == "sdf" and spec.matches(set(properties)):
            return spec
    return None
