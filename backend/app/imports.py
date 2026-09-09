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
from .store import all_rows, find_row, insert_doc, insert_docs_bulk, next_chemical_id, replace_doc
from .utils.excel import parse_csv_rows, sheet_rows_as_dicts
from .utils.registry_templates import RegistrySpec, detect_sdf_spec, detect_sheet_spec
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


# ------------------------------------------------- a recognised source --
def _name_key(name: Any) -> str:
    return " ".join(str(name or "").lower().split())


class _Entry:
    """One registry entry during an import: a database row, or a document not yet written."""

    __slots__ = ("row", "doc", "dirty")

    def __init__(self, row=None, doc: dict[str, Any] | None = None) -> None:
        self.row = row
        self.doc = doc if doc is not None else dict(row.doc)
        self.dirty = row is None


class _Registry:
    """The registry's lookup maps, built once per import and kept current.

    Looking every row up with a query would be one full scan per row, and
    committing every insert on its own is what made a 12,000-row export take
    eight minutes on first try — the pattern of lesson 18. The maps make the
    lookup one pass; new entries are collected and written in batches with
    one commit each; identifiers are allocated from one counter.
    """

    KEYS = ("chemical_id", "dotmatics_reg_id", "dtx_id", "cas_number")

    def __init__(self, db: Session) -> None:
        self.db = db
        self.by: dict[str, dict[str, _Entry]] = {k: {} for k in (*self.KEYS, "name")}
        self.cas_holders: dict[str, set[str]] = {}
        self.entries: dict[str, _Entry] = {}
        self.pending: list[_Entry] = []
        for row in all_rows(db, Chemical):
            self.remember(_Entry(row=row))
        self._next = int(next_chemical_id(db).split("-")[1])

    def allocate_id(self) -> str:
        cid = f"CHEM-{self._next:06d}"
        self._next += 1
        return cid

    def remember(self, entry: _Entry) -> None:
        doc = entry.doc
        cid = doc.get("chemical_id")
        if cid:
            self.entries[cid] = entry
        for key in self.KEYS:
            v = doc.get(key)
            if v not in (None, ""):
                self.by[key].setdefault(str(v), entry)
        if doc.get("name"):
            self.by["name"].setdefault(_name_key(doc["name"]), entry)
        if doc.get("cas_number") and cid:
            self.cas_holders.setdefault(str(doc["cas_number"]), set()).add(cid)

    def find(self, fields: dict[str, Any], order: tuple[str, ...], source: str) -> tuple[_Entry | None, str | None]:
        """The spec's first key is its own identity and always matches. A later
        key (DTXSID, CAS, name) only matches an entry from a DIFFERENT source:
        two registrations of one source that share a DTXSID are two entries,
        kept and flagged, not merged (decision 2 applied to every identifier)."""
        for i, key in enumerate(order):
            v = fields.get(key)
            if v in (None, ""):
                continue
            hit = self.by["name"].get(_name_key(v)) if key == "name" else self.by[key].get(str(v))
            if hit is None:
                continue
            if i > 0 and hit.doc.get("source_template") == source:
                continue
            return hit, key
        return None, None

    def add_new(self, doc: dict[str, Any]) -> _Entry:
        entry = _Entry(row=None, doc=doc)
        self.pending.append(entry)
        self.remember(entry)
        return entry

    def flush(self, batch: int = 1000) -> None:
        """Write everything: new entries in batches, changed rows in one commit."""
        for i in range(0, len(self.pending), batch):
            insert_docs_bulk(self.db, Chemical, [e.doc for e in self.pending[i:i + batch]])
        self.pending = []
        changed = 0
        for entry in self.entries.values():
            if entry.row is not None and entry.dirty:
                replace_doc(self.db, entry.row, entry.doc, commit=False)
                entry.dirty = False
                changed += 1
        if changed:
            self.db.commit()


def import_with_spec(db: Session, spec: RegistrySpec, records: list[dict[str, Any]]) -> dict[str, Any]:
    """Import rows (or SDF molecules) a registry spec recognises.

    Rows sharing the spec's `group_by` value are ONE compound: the first row
    supplies the compound's fields, every row contributes a `batches` entry
    with the batch-level columns, and any other column that differs between
    the rows is recorded under `batch_conflicts` for the audit. An entry is
    matched by the spec's `match_order` (Dotmatics identifier, then DTXSID,
    then CAS, then name — whichever the spec lists); found → updated, else
    inserted with the next sequential identifier. Every column is kept under
    `metadata`.
    """
    registry = _Registry(db)
    groups: list[tuple[Any, list[dict[str, Any]]]] = []
    if spec.group_by:
        index: dict[Any, int] = {}
        for rec in records:
            key = rec.get(spec.group_by)
            if key in (None, ""):
                key = id(rec)
            if key not in index:
                index[key] = len(groups)
                groups.append((key, []))
            groups[index[key]][1].append(rec)
    else:
        groups = [(None, [rec]) for rec in records]

    inserted = updated = 0
    conflicts = pending = 0
    errors: list[dict[str, Any]] = []
    touched_cas: set[str] = set()

    for _key, rows in groups:
        try:
            head = rows[0]
            fields = spec.promote(head)
            metadata = {k: v for k, v in head.items() if v not in (None, "") and not str(k).startswith("_")}
            entry_fields: dict[str, Any] = {**fields, "metadata": metadata, "source_template": spec.key}
            if spec.group_by:
                differing: list[str] = []
                if len(rows) > 1:
                    differing = sorted(
                        k for k in head if k not in spec.batch_fields and len({str(r.get(k)) for r in rows}) > 1
                    )
                # each batch keeps its batch-level columns AND its own value of any
                # column the batches disagree on, so nothing a later batch said is lost
                keep = tuple(spec.batch_fields) + tuple(differing)
                entry_fields["batches"] = [
                    {k: r.get(k) for k in keep if r.get(k) not in (None, "")} for r in rows
                ]
                if differing:
                    entry_fields["batch_conflicts"] = differing
                    conflicts += 1
            if entry_fields.get("nestle_id_pending"):
                pending += 1

            existing, matched_by = registry.find(entry_fields, spec.match_order, spec.key)
            old = existing.doc if existing else None
            doc = {**(old or {}), **entry_fields}
            doc["chemical_id"] = old["chemical_id"] if old else registry.allocate_id()
            doc["id"] = old["id"] if old else str(uuid.uuid4())
            doc["created_at"] = old["created_at"] if old else now_iso()
            doc["updated_at"] = now_iso()
            if doc.get("nestle_id") and doc.get("nestle_id_pending"):
                doc.pop("nestle_id_pending")  # the identifier is already known from another source
                pending -= 1
            if old and matched_by:
                # the first source stays the entry's source; later ones are recorded as merged,
                # and their metadata sits beside the first source's, not over it
                if old.get("source_template") and old["source_template"] != spec.key:
                    doc["source_template"] = old["source_template"]
                    doc["source"] = old.get("source", doc.get("source"))
                    doc["merged_from"] = sorted(set((old.get("merged_from") or []) + [spec.key]))
                    doc["metadata"] = {**(old.get("metadata") or {}), **metadata}
            if doc.get("cas_number"):
                touched_cas.add(str(doc["cas_number"]))
            if existing:
                existing.doc = doc
                existing.dirty = True
                registry.remember(existing)
                updated += 1
            else:
                registry.add_new(doc)
                inserted += 1
        except Exception as err:  # one bad compound must not stop the file
            errors.append({"row": (rows[0].get("CHEMICAL_NAME") or rows[0].get("Chemical name") or f"{spec.group_by}={_key}"), "error": str(err)})

    shared = _flag_shared(registry, "cas_number", "cas_shared_with", touched_cas)
    _flag_shared(registry, "dtx_id", "dtx_shared_with", {str(e.doc.get("dtx_id")) for e in registry.pending if e.doc.get("dtx_id")})
    _flag_shared(registry, "pubchem_cid", "pubchem_shared_with", {str(e.doc.get("pubchem_cid")) for e in registry.pending if e.doc.get("pubchem_cid")})
    registry.flush()
    report = _report(inserted, updated, errors, f" from the {spec.label}")
    report.update({
        "template": spec.key,
        "compounds": len(groups),
        "rows": len(records),
        "batch_conflicts": conflicts,
        "pending_identifiers": pending,
        "cas_shared": shared,
    })
    return report


def _flag_shared(registry: _Registry, field: str, flag: str, values: set[str]) -> int:
    """Decision 2 of CR-9: two entries with one identifier are kept, and both flagged."""
    holders_of: dict[str, set[str]] = {}
    for cid, entry in registry.entries.items():
        v = entry.doc.get(field)
        if v not in (None, ""):
            holders_of.setdefault(str(v), set()).add(cid)
    flagged = 0
    for value in values:
        holders = holders_of.get(value) or set()
        if len(holders) < 2:
            continue
        for cid in holders:
            entry = registry.entries.get(cid)
            if entry is None:
                continue
            others = sorted(holders - {cid})
            if entry.doc.get(flag) != others:
                entry.doc = {**entry.doc, flag: others}
                entry.dirty = True
            flagged += 1
    return flagged


def registry_notices(db: Session) -> dict[str, int]:
    """What the Chemical Registry page keeps showing until someone acts."""
    pending = shared = conflicts = 0
    for row in all_rows(db, Chemical):
        doc = row.doc or {}
        pending += 1 if doc.get("nestle_id_pending") else 0
        shared += 1 if (doc.get("cas_shared_with") or doc.get("dtx_shared_with") or doc.get("pubchem_shared_with")) else 0
        conflicts += 1 if doc.get("batch_conflicts") else 0
    return {"nestle_id_pending": pending, "cas_shared": shared, "batch_conflicts": conflicts}


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

    good = [m for m in molecules if not m.get("_parse_error")]
    spec = detect_sdf_spec(good[0].get("properties") or {}) if good else None
    if spec is not None:
        records = []
        for m in good:
            rec = dict(m.get("properties") or {})
            rec["_mol_block"] = m.get("mol_block")
            rec["_structure"] = m.get("_structure")
            rec["_warnings"] = m.get("warnings") or []
            records.append(rec)
        report = import_with_spec(db, spec, records)
        report["totalRecords"] = len(molecules)
        report["parseErrors"] = len(molecules) - len(good)
        return report

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
        return import_rows(db, data)
    if fmt == "excel":
        data = sheet_rows_as_dicts(content)
        return import_rows(db, data)
    return import_sdf_text(db, content.decode("utf-8", errors="replace"))


def import_rows(db: Session, data: list[dict[str, Any]]) -> dict[str, Any]:
    """Spreadsheet rows: a recognised source goes through its spec, anything else through the generic map."""
    if data:
        spec = detect_sheet_spec(list(data[0].keys()))
        if spec is not None:
            return import_with_spec(db, spec, data)
    return import_spreadsheet_rows(db, data)


def export_chemicals(db: Session) -> list[dict[str, Any]]:
    """Every registry entry as the JSON records ``import_json_records`` accepts, sorted by identifier."""
    docs = [row.doc for row in all_rows(db, Chemical)]
    return sorted(docs, key=lambda d: str(d.get("chemical_id") or ""))
