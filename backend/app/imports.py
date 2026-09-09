"""Every way into the Chemical Registry, through one door.

The browser's upload page, the API's upload endpoints and the terminal
script ``scripts/import_file.py`` all call the functions here, so a file
behaves identically whichever route it arrives by (phase CR-3). Four
formats, one report shape:

* **JSON** — a list of records with the API's own field names
  (``chemical_id``, ``name``, ``cas_number``, ...), or ``{"chemicals": [...]}``.
  This is also what ``scripts/export_chemicals.py`` writes, so an export can
  be reviewed and loaded back without loss.
* **CSV / TSV / XLSX / XLS** — the laboratory's spreadsheet columns, mapped
  by the same column-name chain the upload page has always used.
* **SDF** — structures, through RDKit.

Every route upserts by ``chemical_id``: a record with an identifier the
registry already holds updates that entry; a record without one gets the
next sequential identifier. A record may have no CAS number — that is a
valid entry (decision D3 of the registry-first rule).
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any

from sqlalchemy.orm import Session

from .compat import js_or, now_iso, parse_float_or_none
from .models import Chemical
from .store import all_rows, find_row, insert_doc, next_chemical_id, replace_doc
from .utils.excel import parse_csv_rows, sheet_rows_as_dicts
from .utils.sdf import map_molecule_to_chemical, parse_sdf

FORMATS = {
    ".json": "json",
    ".csv": "csv",
    ".tsv": "csv",
    ".xlsx": "excel",
    ".xls": "excel",
    ".sdf": "sdf",
}

# Fields a JSON record may not set itself: the row's own id and creation time
# belong to the registry, and the identifier is handled separately.
_RESERVED = ("id", "created_at", "updated_at")


class ImportError_(ValueError):
    """A file that cannot be imported at all (empty, wrong format, unreadable)."""


def format_of(filename: str) -> str:
    name = (filename or "").lower()
    for ext, fmt in FORMATS.items():
        if name.endswith(ext):
            return fmt
    raise ImportError_(
        f"Unsupported file type '{filename}': use .json, .csv, .tsv, .xlsx, .xls or .sdf"
    )


def _report(inserted: int, updated: int, errors: list[dict[str, Any]], what: str = "") -> dict[str, Any]:
    response: dict[str, Any] = {
        "message": (
            f"Successfully processed {inserted + updated} chemicals{what} "
            f"({inserted} new, {updated} updated)"
        ),
        "inserted": inserted,
        "updated": updated,
        "total": inserted + updated,
    }
    if errors:
        response["errors"] = errors
    return response


# ------------------------------------------------------------------ JSON --
def parse_json_records(content: bytes | str) -> list[dict[str, Any]]:
    """The records in a JSON upload: a list, or an object with a ``chemicals`` list."""
    text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else content
    try:
        data = json.loads(text)
    except json.JSONDecodeError as err:
        raise ImportError_(f"Not valid JSON: {err.msg} at line {err.lineno}") from None
    if isinstance(data, dict):
        data = data.get("chemicals", data.get("data"))
    if not isinstance(data, list):
        raise ImportError_('JSON must be a list of chemicals, or {"chemicals": [...]}')
    if not data:
        raise ImportError_("JSON file has no chemicals")
    bad = [i for i, r in enumerate(data) if not isinstance(r, dict)]
    if bad:
        raise ImportError_(f"Record #{bad[0] + 1} is not an object")
    return data


def import_json_records(db: Session, records: list[dict[str, Any]]) -> dict[str, Any]:
    """Upsert JSON records. Unknown keys are kept: the document is the record."""
    inserted = updated = 0
    errors: list[dict[str, Any]] = []
    for idx, record in enumerate(records):
        try:
            explicit_id = str(record.get("chemical_id") or "").strip() or None
            existing = find_row(db, Chemical, "chemical_id", explicit_id) if explicit_id else None
            chemical_id = existing.doc["chemical_id"] if existing else (explicit_id or next_chemical_id(db, inserted))
            old = existing.doc if existing else None
            doc = {k: v for k, v in record.items() if k not in _RESERVED}
            doc["chemical_id"] = chemical_id
            doc["name"] = js_or(doc.get("name"), "Unknown")
            if doc.get("cas_number") in ("", None):
                doc["cas_number"] = None  # no CAS is a valid entry
            else:
                doc["cas_number"] = str(doc["cas_number"]).strip()
            doc["id"] = old["id"] if old else str(uuid.uuid4())
            doc["created_at"] = old["created_at"] if old else now_iso()
            doc["updated_at"] = now_iso()
            if existing:
                replace_doc(db, existing, {**old, **doc})
                updated += 1
            else:
                insert_doc(db, Chemical, doc)
                inserted += 1
        except Exception as err:  # one bad record must not stop the file (lesson: batch validation)
            errors.append({"row": record.get("name") or record.get("chemical_id") or f"Record #{idx + 1}", "error": str(err)})
    return _report(inserted, updated, errors)


# ------------------------------------------------------- spreadsheet rows --
def import_spreadsheet_rows(db: Session, data: list[dict[str, Any]]) -> dict[str, Any]:
    """The column-name mapping the upload page has always used, for CSV/TSV/XLSX rows."""
    inserted = updated = 0
    errors: list[dict[str, Any]] = []

    def col(row: dict[str, Any], *names: str) -> str | None:
        """First non-falsy value among the candidate column names (JS `||` chain)."""
        for n in names:
            v = row.get(n)
            if v not in (None, ""):
                return v
        return None

    for row in data:
        try:
            # DTX_ID is an identifier from an external system, kept as its own
            # field. It is NOT the chemical's identity here: a compound with no
            # DTX_ID must show an empty one rather than an invented value.
            dtx_id = col(row, "DTX_ID", "dtx_id", "Dtx_ID", "DTXSID", "dtxsid")
            explicit_id = col(row, "chemical_id", "Chemical_ID")

            # Re-uploading matches on whichever identifier the file carries, so
            # an upload still updates rather than duplicating.
            existing = None
            if explicit_id:
                existing = find_row(db, Chemical, "chemical_id", explicit_id)
            if existing is None and dtx_id:
                existing = next(
                    (r for r in all_rows(db, Chemical) if r.doc.get("dtx_id") == dtx_id),
                    None,
                )
            chemical_id = (
                existing.doc["chemical_id"]
                if existing
                else (explicit_id or next_chemical_id(db, inserted))
            )
            nestle_id = col(row, "NESTLE_ID", "Nestle_ID", "nestle_id")
            cas_number = col(row, "CAS_NO", "CAS_Number", "cas_no", "cas_number", "CAS")
            name = col(row, "CHEMICAL_NAME", "Chemical_Name", "chemical_name",
                       "Name", "name") or "Unknown"
            mol_weight = col(row, "MOL_WEIGHT_ORIG", "MOL_WEIGHT", "Mol_Weight", "mol_weight",
                             "MW", "molecular_weight", "Molecular_Weight")
            mol_formula = col(row, "MOL_FORMULA", "MOL_FOR", "Mol_For", "mol_for",
                              "molecular_formula", "Molecular_Formula", "Formula")
            supplier_ref = col(row, "Supplier_ref", "SUPPLIER_REF", "supplier_ref",
                               "Supplier", "supplier")

            old = existing.doc if existing else None

            chemical = {
                "id": old["id"] if old else str(uuid.uuid4()),
                "chemical_id": chemical_id,
                "dtx_id": dtx_id,
                "nestle_id": nestle_id,
                "name": name,
                "cas_number": str(cas_number) if cas_number else None,
                "molecular_formula": mol_formula,
                "molecular_weight": parse_float_or_none(mol_weight) if mol_weight else None,
                "smiles": col(row, "SMILES", "smiles"),
                "inchi": col(row, "InChI", "inchi"),
                "inchi_key": col(row, "InChIKey", "inchi_key"),
                "supplier": supplier_ref,
                "description": col(row, "Description", "description"),
                "metadata": row,
                "created_at": old["created_at"] if old else now_iso(),
                "updated_at": now_iso(),
            }

            if existing:
                replace_doc(db, existing, chemical)
                updated += 1
            else:
                insert_doc(db, Chemical, chemical)
                inserted += 1
        except Exception as err:
            errors.append(
                {"row": row.get("CHEMICAL_NAME") or row.get("Name") or "Unknown", "error": str(err)}
            )
    return _report(inserted, updated, errors)


# ------------------------------------------------------------------- SDF --
def import_sdf_text(db: Session, sdf_content: str) -> dict[str, Any]:
    """Structures through RDKit; keeps the SDF endpoint's richer report shape."""
    molecules = parse_sdf(sdf_content)
    if not molecules:
        raise ImportError_(
            "No valid molecules found in the SDF file. Ensure the file follows "
            "the V2000/V3000 SDF format with $$$$ record delimiters."
        )

    inserted = updated = 0
    parse_errors: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for idx, mol in enumerate(molecules):
        if mol.get("_parse_error"):
            parse_errors.append(
                {
                    "molecule": f"Record #{idx + 1}",
                    "error": "; ".join(mol.get("warnings") or []) or "Failed to parse",
                }
            )
            continue

        try:
            mapped = map_molecule_to_chemical(mol)
            # Generate a chemical_id if not found in the SDF properties
            # (JS used Date.now(); epoch-millis here for the same shape).
            chemical_id = mapped.get("chemical_id") or f"SDF-{int(time.time() * 1000)}-{idx}"

            existing = find_row(db, Chemical, "chemical_id", chemical_id)
            old = existing.doc if existing else None

            chemical = {
                "id": old["id"] if old else str(uuid.uuid4()),
                "chemical_id": chemical_id,
                "nestle_id": js_or(mapped.get("nestle_id"), None),
                "name": js_or(mapped.get("name"), "Unknown"),
                "cas_number": js_or(mapped.get("cas_number"), None),
                "molecular_formula": js_or(mapped.get("molecular_formula"), None),
                "molecular_weight": js_or(mapped.get("molecular_weight"), None),
                "smiles": js_or(mapped.get("smiles"), None),
                "inchi": js_or(mapped.get("inchi"), None),
                "inchi_key": js_or(mapped.get("inchi_key"), None),
                "supplier": js_or(mapped.get("supplier"), None),
                "purity": js_or(mapped.get("purity"), None),
                "storage_conditions": js_or(mapped.get("storage_conditions"), None),
                "hazard_info": js_or(mapped.get("hazard_info"), None),
                "description": js_or(mapped.get("description"), None),
                "mol_block": js_or(mapped.get("mol_block"), None),
                "metadata": mapped.get("metadata") or {},
                "dtxsid": js_or(mapped.get("dtxsid"), None),
                "preferred_name": js_or(mapped.get("preferred_name"), None),
                "monoisotopic_mass": js_or(mapped.get("monoisotopic_mass"), None),
                "ms_ready_smiles": js_or(mapped.get("ms_ready_smiles"), None),
                "inchi_string": js_or(mapped.get("inchi_string"), None),
                "synonyms": mapped.get("synonyms") or [],
                "structural": js_or(mapped.get("structural"), None),
                "created_at": old["created_at"] if old else now_iso(),
                "updated_at": now_iso(),
            }

            if existing:
                replace_doc(db, existing, chemical)
                updated += 1
            else:
                insert_doc(db, Chemical, chemical)
                inserted += 1
        except Exception as err:
            errors.append({"molecule": mol.get("name") or f"Record #{idx + 1}", "error": str(err)})

    all_errors = parse_errors + errors
    response: dict[str, Any] = {
        "message": (
            f"Successfully processed {inserted + updated} chemicals from SDF "
            f"({inserted} new, {updated} updated)"
        ),
        "inserted": inserted,
        "updated": updated,
        "total": inserted + updated,
        "totalRecords": len(molecules),
        "summary": {
            "recordsInFile": len(molecules),
            "successfullyProcessed": inserted + updated,
            "parseErrors": len(parse_errors),
            "insertErrors": len(errors),
        },
    }
    if all_errors:  # v1 omits the key when empty (undefined)
        response["errors"] = all_errors
    return response


# ------------------------------------------------------------ one door --
def import_chemicals_file(db: Session, filename: str, content: bytes) -> dict[str, Any]:
    """Import a chemicals file of any supported format; the report says what happened.

    Raises ``ImportError_`` when the file cannot be imported at all; per-record
    problems are listed under ``errors`` in the report instead.
    """
    fmt = format_of(filename)
    if fmt == "json":
        return import_json_records(db, parse_json_records(content))
    if fmt == "csv":
        data = parse_csv_rows(content.decode("utf-8", errors="replace"))
        if not data:
            raise ImportError_("CSV file is empty or has no data rows")
        return import_spreadsheet_rows(db, data)
    if fmt == "excel":
        data = sheet_rows_as_dicts(content)
        return import_spreadsheet_rows(db, data)
    return import_sdf_text(db, content.decode("utf-8", errors="replace"))


def export_chemicals(db: Session) -> list[dict[str, Any]]:
    """Every registry entry as the JSON records ``import_json_records`` accepts, sorted by identifier."""
    docs = [row.doc for row in all_rows(db, Chemical)]
    return sorted(docs, key=lambda d: str(d.get("chemical_id") or ""))
