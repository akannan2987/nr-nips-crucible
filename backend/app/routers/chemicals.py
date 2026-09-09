"""/api/chemicals — chemicals resource endpoints.

Every endpoint mirrors the legacy (v1) contract: same paths, same response
shapes, same messages, same status codes — including the quirks (the
`errors` key is omitted when empty; `|| null` coerces '' and 0 to null).
"""

import json
import uuid
from typing import Any

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..compat import (
    js_or,
    now_iso,
    parse_int_or,
    sort_created_desc,
    total_pages,
)
from ..database import get_db
from ..imports import (
    ImportError_,
    import_chemicals_file,
    import_json_records,
    import_sdf_text,
    parse_json_records,
    registry_notices,
)
from ..links import count_links, describe_links, unlink_targets
from ..models import Chemical
from ..schemas import BulkDeleteChemicals, BulkUpdateChemicals, ChemicalIn
from ..store import (
    all_docs,
    clear_all,
    delete_row,
    find_row,
    insert_doc,
    replace_doc,
)

router = APIRouter(prefix="/api/chemicals", tags=["chemicals"])


_COLUMNS_CACHE: dict[str, Any] = {}

# Keys never offered as table columns: the row's own id, and the large nested
# values that have their own presentation (batches as a view, the structure
# as a drawing, metadata as its own dotted columns).
_INTERNAL = {"id", "batches", "metadata", "structural", "mol_block", "structure_warnings"}


def _value(doc: dict[str, Any], key: str) -> Any:
    """A column's value, including dotted keys: `metadata.CAS_NO`, `batch.BATCH_ID`."""
    if "." in key:
        head, tail = key.split(".", 1)
        inner = doc.get(head)
        return inner.get(tail) if isinstance(inner, dict) else None
    return doc.get(key)


def _batch_rows(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per batch: the compound's fields plus `batch.<column>` and a position.

    A compound with no batches (a generic upload, the limited list) is one row
    with `batch` empty, so the view is still every compound.
    """
    rows: list[dict[str, Any]] = []
    for doc in docs:
        batches = doc.get("batches") or [{}]
        for i, batch in enumerate(batches, start=1):
            rows.append({**doc, "batch": batch, "batch_no": i, "batches_total": len(batches)})
    return rows


def _filtered(docs: list[dict[str, Any]], needle: str, filters: dict[str, str]) -> list[dict[str, Any]]:
    if needle:
        docs = [
            c
            for c in docs
            if (c.get("name") and needle in str(c["name"]).lower())
            or (c.get("chemical_id") and needle in str(c["chemical_id"]).lower())
            or (c.get("cas_number") and needle in str(c["cas_number"]).lower())
        ]
    for key, term in filters.items():
        term_l = str(term).lower()
        docs = [c for c in docs if term_l in str(_value(c, key) if _value(c, key) is not None else "").lower()]
    return docs


def _sorted(docs: list[dict[str, Any]], sort: str | None, order: str | None) -> list[dict[str, Any]]:
    if not sort:
        return sort_created_desc(docs)
    reverse = (order or "asc").lower() == "desc"
    values = [(_value(d, sort), d) for d in docs]
    numeric = all(isinstance(v, (int, float)) or v in (None, "") for v, _ in values) and any(
        isinstance(v, (int, float)) for v, _ in values
    )

    def missing(v: Any) -> bool:
        return v in (None, "", [], {})

    present = [(v, d) for v, d in values if not missing(v)]
    absent = [d for v, d in values if missing(v)]
    key = (lambda pair: float(pair[0])) if numeric else (lambda pair: str(pair[0]).lower())
    ordered = [d for _, d in sorted(present, key=key, reverse=reverse)]
    return ordered + absent  # missing values last in BOTH directions


@router.get("")
def list_chemicals(
    page: str | None = None,
    limit: str | None = None,
    search: str | None = None,
    view: str | None = None,
    sort: str | None = None,
    order: str | None = None,
    filters: str | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """GET /api/chemicals — paginated list with optional search.

    Since v2.15.0 (phase CR-2, with CR-1's sorting and per-column filters):
    `view=batches` answers one row per batch (`batch.<column>`, `batch_no`,
    `batches_total`) instead of one per compound; `sort=<key>&order=asc|desc`
    orders by any column, dotted keys included (`metadata.CAS_NO`), numbers
    as numbers, missing values last; `filters={"key": "text", …}` keeps the
    rows whose column contains the text, case-insensitively. Without these
    parameters the answer is exactly what it always was.
    """
    page_n = parse_int_or(page, 1)
    limit_n = parse_int_or(limit, 50)
    needle = (search or "").lower()
    offset = (page_n - 1) * limit_n
    try:
        filter_map = {str(k): str(v) for k, v in (json.loads(filters) if filters else {}).items() if str(v)}
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="filters must be a JSON object of column: text") from None

    chemicals = all_docs(db, Chemical)
    if view == "batches":
        chemicals = _batch_rows(chemicals)
    chemicals = _filtered(chemicals, needle, filter_map)
    chemicals = _sorted(chemicals, sort, order)
    total = len(chemicals)
    page_items = chemicals[offset : offset + limit_n]

    return {
        "data": page_items,
        "pagination": {
            "page": page_n,
            "limit": limit_n,
            "total": total,
            "totalPages": total_pages(total, limit_n),
        },
    }


@router.get("/columns")
def chemical_columns(db: Session = Depends(get_db)) -> dict[str, Any]:
    """GET /api/chemicals/columns — every column the stored entries actually have (CR-2).

    Top-level fields in first-seen order, then every key kept under `metadata`
    as `metadata.<key>`, then every key seen inside `batches` as `batch.<key>`;
    each with how many entries carry a value. Cached against the entry count,
    like the screening table's columns.
    """
    count = db.scalar(select(func.count()).select_from(Chemical)) or 0
    cached = _COLUMNS_CACHE.get("payload")
    if cached is not None and _COLUMNS_CACHE.get("key") == count:
        return cached

    docs = all_docs(db, Chemical)
    order: list[str] = []
    filled: dict[str, int] = {}
    batch_keys: list[str] = []

    def note(key: str, value: Any) -> None:
        if key not in filled:
            order.append(key)
            filled[key] = 0
        if value not in (None, "", [], {}):
            filled[key] += 1

    for doc in docs:
        for key, value in doc.items():
            if key not in _INTERNAL:
                note(key, value)
        for key, value in (doc.get("metadata") or {}).items():
            note(f"metadata.{key}", value)
        for batch in doc.get("batches") or []:
            for key in batch:
                if key not in batch_keys:
                    batch_keys.append(key)

    payload = {
        "total": len(docs),
        "columns": [
            {"key": k, "label": k.split(".", 1)[1] if k.startswith("metadata.") else k, "group": "metadata" if k.startswith("metadata.") else "field",
             "filled": filled[k], "coverage": round(filled[k] / len(docs), 4) if docs else 0}
            for k in order
        ],
        "batch_columns": [{"key": f"batch.{k}", "label": k} for k in batch_keys],
    }
    _COLUMNS_CACHE["key"] = count
    _COLUMNS_CACHE["payload"] = payload
    return payload


@router.get("/list/dropdown")
def chemicals_dropdown(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """GET /api/chemicals/list/dropdown — {chemical_id, name} sorted by name."""
    chemicals = all_docs(db, Chemical)
    items = [{"chemical_id": c.get("chemical_id"), "name": c.get("name")} for c in chemicals]
    # The v1 API used localeCompare (case-insensitive-ish); lower() is the
    # closest deterministic equivalent.
    items.sort(key=lambda x: str(x["name"] or "").lower())
    return items


@router.post("", status_code=201)
def add_chemical(body: ChemicalIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    """POST /api/chemicals — add one chemical (400 on duplicate chemical_id)."""
    existing = find_row(db, Chemical, "chemical_id", body.chemical_id)
    if existing:
        raise HTTPException(status_code=400, detail="Chemical ID already exists")

    chemical = {
        "id": str(uuid.uuid4()),
        "chemical_id": body.chemical_id,
        "nestle_id": js_or(body.nestle_id, None),
        "name": body.name,
        "cas_number": js_or(body.cas_number, None),
        "molecular_formula": js_or(body.molecular_formula, None),
        "molecular_weight": js_or(body.molecular_weight, None),
        "smiles": js_or(body.smiles, None),
        "inchi": js_or(body.inchi, None),
        "inchi_key": js_or(body.inchi_key, None),
        "supplier": js_or(body.supplier, None),
        "description": js_or(body.description, None),
        "metadata": js_or(body.metadata, None),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    insert_doc(db, Chemical, chemical)
    return {"message": "Chemical added successfully", "chemical_id": chemical["chemical_id"]}


@router.post("/upload/sdf")
async def upload_sdf(
    file: UploadFile | None = File(default=None), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """POST /api/chemicals/upload/sdf — bulk import from an SDF file (through app.imports)."""
    if file is None:
        raise HTTPException(status_code=400, detail="No file uploaded")
    content = await file.read()
    try:
        return import_sdf_text(db, content.decode("utf-8", errors="replace"))
    except ImportError_ as err:
        raise HTTPException(status_code=400, detail=str(err)) from None


@router.post("/upload/excel")
async def upload_excel(
    file: UploadFile | None = File(default=None), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """POST /api/chemicals/upload/excel — bulk import from Excel/CSV (through app.imports)."""
    if file is None:
        raise HTTPException(status_code=400, detail="No file uploaded")
    file_name = (file.filename or "").lower()
    content = await file.read()
    try:
        if file_name.endswith(".csv") or file_name.endswith(".tsv"):
            return import_chemicals_file(db, file_name, content)
        return import_chemicals_file(db, file_name if file_name.endswith((".xlsx", ".xls")) else "upload.xlsx", content)
    except ImportError_ as err:
        raise HTTPException(status_code=400, detail=str(err)) from None


@router.post("/upload/json")
async def upload_json(
    file: UploadFile | None = File(default=None), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """POST /api/chemicals/upload/json — bulk import from a JSON file (CR-3).

    The file holds a list of chemicals with the API's own field names, or
    ``{"chemicals": [...]}`` — the shape ``scripts/export_chemicals.py`` writes.
    """
    if file is None:
        raise HTTPException(status_code=400, detail="No file uploaded")
    content = await file.read()
    try:
        return import_json_records(db, parse_json_records(content))
    except ImportError_ as err:
        raise HTTPException(status_code=400, detail=str(err)) from None


@router.post("/import")
def import_json_body(payload: Any = Body(default=None), db: Session = Depends(get_db)) -> dict[str, Any]:
    """POST /api/chemicals/import — the same as upload/json, with the records in the request body.

    For scripts that build the list themselves: ``{"chemicals": [...]}`` or a bare list.
    """
    if payload is None:
        raise HTTPException(status_code=400, detail="No chemicals provided")
    try:
        return import_json_records(db, parse_json_records(json.dumps(payload)))
    except ImportError_ as err:
        raise HTTPException(status_code=400, detail=str(err)) from None


def _refuse_or_unlink(db: Session, targets: set[str] | None, force: bool, what: str) -> dict[str, int] | None:
    """The CR-6 rule, shared by every deletion route.

    Rows still pointing at the chemical(s) make a plain delete a **409**: the
    caller — a person in the browser, or a script that did not say it knows —
    is told how many and sent to unlink them first. With `force` the rows are
    unlinked here, then the caller deletes; always in that order, so a failure
    between the two halves leaves rows showing their source names rather than
    pointing at nothing (lesson 22). Returns the unlink counts when forced,
    None when nothing was linked.
    """
    counts = count_links(db, targets)
    if counts["total"] == 0:
        return None
    if not force:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{describe_links(counts)} linked to {what}; unlink them first "
                "(Screening Data page, or POST /api/screening/unlink), or pass force=true "
                "to unlink and then delete."
            ),
        )
    return unlink_targets(db, targets)


@router.post("/bulk/delete")
def bulk_delete(body: BulkDeleteChemicals, db: Session = Depends(get_db)) -> dict[str, Any]:
    """POST /api/chemicals/bulk/delete — refuses while rows are linked unless `force`."""
    ids = body.chemical_ids
    if not ids or not isinstance(ids, list) or len(ids) == 0:
        raise HTTPException(status_code=400, detail="No chemical IDs provided")

    present = [cid for cid in ids if find_row(db, Chemical, "chemical_id", cid)]
    unlinked = _refuse_or_unlink(db, set(present), bool(body.force), f"{len(present)} of the {len(ids)} chemicals")

    deleted = 0
    for cid in ids:
        row = find_row(db, Chemical, "chemical_id", cid)
        if row:
            delete_row(db, row)
            deleted += 1

    response: dict[str, Any] = {
        "message": f"Successfully deleted {deleted} chemicals",
        "deleted": deleted,
        "requested": len(ids),
    }
    if unlinked:
        response["unlinked"] = unlinked
    return response


@router.post("/bulk/update")
def bulk_update(body: BulkUpdateChemicals, db: Session = Depends(get_db)) -> dict[str, Any]:
    """POST /api/chemicals/bulk/update — same updates applied to many records."""
    ids = body.chemical_ids
    updates = dict(body.updates or {})
    if not ids or not isinstance(ids, list) or len(ids) == 0:
        raise HTTPException(status_code=400, detail="No chemical IDs provided")
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    # Never allow changing identity/audit fields (same guard as the v1 API).
    for protected in ("chemical_id", "id", "created_at"):
        updates.pop(protected, None)

    updated = 0
    for cid in ids:
        row = find_row(db, Chemical, "chemical_id", cid)
        if row:
            replace_doc(db, row, {**row.doc, **updates, "updated_at": now_iso()})
            updated += 1

    return {
        "message": f"Successfully updated {updated} chemicals",
        "updated": updated,
        "requested": len(ids),
    }


@router.delete("/all/clear")
def clear_chemicals(
    force: bool = Query(default=False), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """DELETE /api/chemicals/all/clear — remove every chemical; refuses while any row is linked unless `force`."""
    unlinked = _refuse_or_unlink(db, None, force, "chemicals")
    count = clear_all(db, Chemical)
    response: dict[str, Any] = {"message": f"Successfully deleted all {count} chemicals", "deleted": count}
    if unlinked:
        response["unlinked"] = unlinked
    return response


@router.get("/notices/summary")
def notices(db: Session = Depends(get_db)) -> dict[str, int]:
    """GET /api/chemicals/notices/summary — what the registry page keeps showing until someone acts (CR-9)."""
    return registry_notices(db)


@router.get("/{chemical_id}")
def get_chemical(chemical_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """GET /api/chemicals/:id — one chemical by its chemical_id."""
    row = find_row(db, Chemical, "chemical_id", chemical_id)
    if not row:
        raise HTTPException(status_code=404, detail="Chemical not found")
    return row.doc


@router.put("/{chemical_id}")
def update_chemical(
    chemical_id: str,
    payload: dict[str, Any] = Body(default={}),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """PUT /api/chemicals/:id — merge arbitrary fields into the record.

    The v1 API merged the whole request body (`.assign({...req.body})`), so the
    body is a free-form dict here on purpose — there is no fixed schema.
    """
    row = find_row(db, Chemical, "chemical_id", chemical_id)
    if not row:
        raise HTTPException(status_code=404, detail="Chemical not found")
    replace_doc(db, row, {**row.doc, **payload, "updated_at": now_iso()})
    return {"message": "Chemical updated successfully"}


@router.delete("/{chemical_id}")
def delete_chemical(
    chemical_id: str, force: bool = Query(default=False), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """DELETE /api/chemicals/:id — refuses while rows are linked unless `force`."""
    row = find_row(db, Chemical, "chemical_id", chemical_id)
    if not row:
        raise HTTPException(status_code=404, detail="Chemical not found")
    unlinked = _refuse_or_unlink(db, {chemical_id}, force, chemical_id)
    delete_row(db, row)
    response: dict[str, Any] = {"message": "Chemical deleted successfully"}
    if unlinked:
        response["unlinked"] = unlinked
    return response
