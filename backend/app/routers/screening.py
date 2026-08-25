"""/api/screening — screening resource endpoints."""

import csv
import io
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import Float, String, case, cast, func, select
from sqlalchemy.orm import Session

from ..compat import js_or, now_iso, parse_int_or, total_pages
from ..database import get_db
from ..ingest import load_screening
from ..models import Chemical, Screening
from ..schemas import ScreeningIn
from ..store import all_docs, delete_row, find_row, insert_doc, replace_doc
from ..utils.excel import sheet_rows_as_dicts
from ..utils.templates import (
    describe_column,
    label_for,
    detect_template,
    parse_with_spec,
    source_column_for,
)

router = APIRouter(prefix="/api/screening", tags=["screening"])


def _chemical_name_map(db: Session) -> dict[Optional[str], str]:
    return {c.get("chemical_id"): c.get("name") for c in all_docs(db, Chemical)}


# Keys that are structural rather than data, so the table does not offer them
# as columns to display.
_INTERNAL_KEYS = {
    "id",
    "raw",
    "source",
    "updated_at",
    # Duplicate bookkeeping drives row shading and the unique-only filter in
    # the table; it is not information from the file, so it is not a column.
    "duplicate_group",
    "duplicate_kind",
    "duplicate_rank",
    # An internal link, not information from the file. The Chemical column
    # shows the compound and links through to the Chemicals module when the
    # compound has been identified.
    "chemical_id",
}

# Column metadata is expensive to compute and changes only when rows do, so it
# is cached in the process and keyed on the row count.
_COLUMNS_CACHE: dict[str, Any] = {}


def _order_by(statement, sort: Optional[str], direction: str, numeric: bool):
    """Order by any column, in the database.

    Sorting happens in SQL for the same reason filtering does — pulling 49,000
    documents into Python to sort them is what made the table unusable. Numeric
    columns are cast to a number first, so 100 does not sort before 20.

    Empty values are pushed to the end in both directions: a blank cell is
    absence of information, and burying the populated rows under thousands of
    blanks is never what someone clicking a heading wants.
    """
    if not sort:
        return statement.order_by(Screening.seq.desc())

    value = Screening.doc[sort].as_string()
    is_empty = case((value.is_(None), 1), (value == "", 1), else_=0)
    key = cast(value, Float) if numeric else func.lower(value)
    return statement.order_by(is_empty, key.desc() if direction == "desc" else key.asc())


def _apply_filters(
    statement,
    search: Optional[str],
    chemical_id: Optional[str],
    tag: Optional[str],
    filters: dict[str, str],
    duplicates: Optional[str] = None,
):
    """Add the requested filters to a SQL statement, or return None.

    Filtering inside the database instead of in Python is the difference
    between a table that responds and one that does not: reading all 49,000
    documents into Python to filter them takes seconds, whereas SQLite reads
    the same values with `json_extract` in a fraction of that.

    `doc[key].as_string()` is SQLAlchemy's dialect-neutral JSON access — it
    renders `json_extract(...)` on SQLite and `->>` on PostgreSQL, so this
    works on both without a branch.

    Returns None when there is nothing to filter, letting the caller take the
    plain paginated path.
    """
    if not (search or chemical_id or tag or filters or (duplicates and duplicates != "all")):
        return None

    if duplicates and duplicates != "all":
        kind = Screening.doc["duplicate_kind"].as_string()
        rank = Screening.doc["duplicate_rank"].as_string()
        if duplicates == "unique":
            # Drop only the extra copies of rows whose every source value
            # matched. Repeat measurements are kept: they are results, not
            # duplication. `duplicate_rank` 0 is the first of each copy group.
            statement = statement.where(
                (kind.is_(None)) | (kind != "identical") | (rank == "0")
            )
        elif duplicates == "identical":
            statement = statement.where(kind == "identical")
        elif duplicates == "repeat":
            statement = statement.where(kind == "repeat_measurement")
        elif duplicates == "flagged":
            statement = statement.where(kind.is_not(None))

    if chemical_id:
        statement = statement.where(Screening.chemical_id == chemical_id)

    if tag:
        statement = statement.where(Screening.doc["source"]["tag"].as_string() == tag)

    for key, value in (filters or {}).items():
        # Case-insensitive substring, which is what someone scanning a table
        # expects — exact matching on free-typed laboratory text finds nothing.
        column = func.lower(Screening.doc[key].as_string())
        statement = statement.where(column.like(f"%{str(value).lower()}%"))

    if search:
        # Free text searches the whole document. Records from different
        # templates share almost no field names, so searching a fixed list of
        # columns could only ever find one template's data.
        whole = func.lower(func.cast(Screening.doc, String))
        statement = statement.where(whole.like(f"%{search.lower()}%"))

    return statement


def _column_order(docs: list[dict[str, Any]]) -> list[str]:
    """Every column present across the records, in first-seen order.

    First-seen order matters: it reproduces the left-to-right order of the
    original spreadsheet, because the template spec declares its fields in that
    order. An alphabetical list would scramble a layout the user recognises.
    """
    seen: list[str] = []
    for doc in docs:
        for key in doc:
            if key not in _INTERNAL_KEYS and key not in seen:
                seen.append(key)
    return seen


@router.get("")
def list_screening(
    request: Request,
    page: Optional[str] = None,
    limit: Optional[str] = None,
    search: Optional[str] = None,
    chemical_id: Optional[str] = None,
    tag: Optional[str] = None,
    sort: Optional[str] = None,
    dir: str = "asc",
    # Taken as text, not bool: browsers send empty strings for unset parameters
    # and FastAPI rejects "" as a boolean, which would fail the whole request.
    sort_numeric: Optional[str] = None,
    # all | unique | identical | repeat | flagged
    duplicates: Optional[str] = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """GET /api/screening — paginated list, filterable, sortable, enriched.

    Accepts `?f.<column>=<value>` for per-column filtering, in addition to the
    free-text `search`, a `tag` (data source) and `chemical_id`.
    """
    page_n = parse_int_or(page, 1)
    limit_n = parse_int_or(limit, 50)
    offset = (page_n - 1) * limit_n
    filters = {k[2:]: v for k, v in request.query_params.items() if k.startswith("f.") and v}

    statement = _apply_filters(select(Screening), search, chemical_id, tag, filters, duplicates)
    if statement is not None:
        # Filters were expressible in SQL, so the database does the work.
        total = db.scalar(
            select(func.count()).select_from(
                _apply_filters(
                    select(Screening.id), search, chemical_id, tag, filters, duplicates
                ).subquery()
            )
        ) or 0
        rows = db.scalars(
            _order_by(statement, sort, dir, sort_numeric in ("true", "1", "yes")).offset(offset).limit(limit_n)
        )
        page_items = [row.doc for row in rows]
    else:
        # Nothing to filter: the database answers with COUNT and LIMIT/OFFSET.
        total = db.scalar(select(func.count()).select_from(Screening)) or 0
        rows = db.scalars(
            _order_by(select(Screening), sort, dir, sort_numeric in ("true", "1", "yes"))
            .offset(offset)
            .limit(limit_n)
        )
        page_items = [row.doc for row in rows]

    names = _chemical_name_map(db)
    # `raw` is dropped from list responses: it roughly doubles the payload and
    # the table never shows it. The detail endpoint returns the full record,
    # original row included.
    enriched = [
        {
            **{k: v for k, v in s.items() if k != "raw"},
            "chemical_name": names.get(s.get("chemical_id"), "Unknown") or "Unknown",
        }
        for s in page_items
    ]

    return {
        "data": enriched,
        "pagination": {
            "page": page_n,
            "limit": limit_n,
            "total": total,
            "totalPages": total_pages(total, limit_n),
        },
    }


@router.get("/duplicates/summary")
def duplicates_summary(db: Session = Depends(get_db)) -> dict[str, Any]:
    """GET /api/screening/duplicates/summary — how many rows are in each state.

    Lets the interface label its filter with real numbers rather than making
    someone select an option to discover it matches nothing.
    """
    kind = Screening.doc["duplicate_kind"].as_string()
    total = db.scalar(select(func.count()).select_from(Screening)) or 0
    identical = db.scalar(
        select(func.count()).select_from(Screening).where(kind == "identical")
    ) or 0
    repeat = db.scalar(
        select(func.count()).select_from(Screening).where(kind == "repeat_measurement")
    ) or 0
    # Removing the extra copies leaves one row per identical group.
    rank = Screening.doc["duplicate_rank"].as_string()
    unique = db.scalar(
        select(func.count())
        .select_from(Screening)
        .where((kind.is_(None)) | (kind != "identical") | (rank == "0"))
    ) or 0
    return {
        "total": total,
        "identical": identical,
        "repeat_measurement": repeat,
        "unique": unique,
        "copies_removed_by_unique": total - unique,
    }


@router.get("/columns")
def screening_columns(db: Session = Depends(get_db)) -> dict[str, Any]:
    """GET /api/screening/columns — what columns the stored records actually have.

    The table is built from this rather than from a fixed list, because records
    loaded from different laboratory templates share almost no field names.
    `filled` (how many records carry a value) lets the interface offer a
    sensible default selection instead of showing 25 columns half of which are
    empty.
    """
    # Working out coverage means reading every document, which takes seconds on
    # a large table. The answer only changes when rows are added or removed, so
    # it is cached against the row count — a new upload or a delete changes the
    # count and the next call recomputes.
    # Keyed on the chemical count as well as the screening count: identifying
    # compounds changes how many rows are linked without changing how many rows
    # exist, so a screening-only key would serve a stale "0 identified" long
    # after identification had run.
    count = db.scalar(select(func.count()).select_from(Screening)) or 0
    chem_count = db.scalar(select(func.count()).select_from(Chemical)) or 0
    key = (count, chem_count)
    cached = _COLUMNS_CACHE.get("payload")
    if cached is not None and _COLUMNS_CACHE.get("key") == key:
        return cached

    docs = all_docs(db, Screening)
    order = _column_order(docs)
    filled = {name: 0 for name in order}
    for doc in docs:
        for name in order:
            value = doc.get(name)
            if value not in (None, "", [], {}):
                filled[name] += 1

    tags = sorted({(d.get("source") or {}).get("tag") for d in docs} - {None})
    # How many rows point at a registered compound. Identification is a
    # separate step from import, so without this the interface gives no hint
    # that anything is outstanding — it simply shows plain names and looks
    # finished.
    identified = sum(1 for d in docs if d.get("chemical_id"))

    payload = {
        "total": len(docs),
        "tags": tags,
        "identified": identified,
        "unidentified": len(docs) - identified,
        "columns": [
            {
                "key": name,
                # The heading the source file used, so the table reads like the
                # spreadsheet it came from. Columns this application added have
                # no source heading and are labelled and described instead.
                "label": label_for(name),
                "source_column": source_column_for(name),
                "derived": source_column_for(name) is None,
                "description": describe_column(name),
                "type": _infer_type(docs, name),
                "filled": filled[name],
                "coverage": round(filled[name] / len(docs), 4) if docs else 0,
            }
            for name in order
        ],
    }
    _COLUMNS_CACHE["key"] = key
    _COLUMNS_CACHE["payload"] = payload
    return payload


def _infer_type(docs: list[dict[str, Any]], name: str) -> str:
    """Guess a column's type from its values, so sorting behaves sensibly.

    Sorting numbers as text puts 100 before 20, which looks like a bug to
    anyone reading the table. Only a sample is inspected — enough to classify a
    column without another full scan.
    """
    seen = 0
    numeric = booleans = 0
    for doc in docs:
        value = doc.get(name)
        if value in (None, "", [], {}):
            continue
        seen += 1
        if isinstance(value, bool):
            booleans += 1
        elif isinstance(value, (int, float)):
            numeric += 1
        if seen >= 200:
            break
    if seen == 0:
        return "text"
    if booleans == seen:
        return "boolean"
    if numeric == seen:
        return "number"
    return "text"


def _humanise(key: str) -> str:
    """`mg_per_kg_food` → `Mg Per Kg Food`, for column headings."""
    return key.replace("_", " ").strip().title()


def _filtered_docs(
    db: Session,
    search: Optional[str],
    chemical_id: Optional[str],
    tag: Optional[str],
    filters: dict[str, str],
    duplicates: Optional[str] = None,
) -> list[dict[str, Any]]:
    """The same selection the table shows, for export — filtered in SQL."""
    statement = _apply_filters(select(Screening), search, chemical_id, tag, filters, duplicates)
    if statement is None:
        statement = select(Screening)
    return [row.doc for row in db.scalars(statement.order_by(Screening.seq.desc()))]


@router.get("/export")
def export_screening(
    request: Request,
    format: str = "csv",
    columns: Optional[str] = None,
    search: Optional[str] = None,
    chemical_id: Optional[str] = None,
    tag: Optional[str] = None,
    raw: bool = False,
    duplicates: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """GET /api/screening/export — download the current selection as a file.

    `format` is `csv`, `xlsx` or `json`. `columns` is an optional comma-separated
    list; omitted, every column is exported. `raw=true` exports the untouched
    original values instead of the cleaned ones, which is what you want when
    handing the file to someone who needs to reconcile it against the source.

    Export applies the *same* filters as the table, so what you download is
    what you were looking at — the whole selection, not just the page on screen.
    """
    filters = {k[2:]: v for k, v in request.query_params.items() if k.startswith("f.") and v}
    docs = _filtered_docs(db, search, chemical_id, tag, filters, duplicates)

    names = _chemical_name_map(db)
    rows: list[dict[str, Any]] = []
    for doc in docs:
        if raw:
            row = dict(doc.get("raw") or {})
        else:
            row = {k: v for k, v in doc.items() if k not in _INTERNAL_KEYS}
            row["chemical_name"] = names.get(doc.get("chemical_id"), "Unknown") or "Unknown"
        rows.append(row)

    if columns:
        wanted = [c for c in columns.split(",") if c]
        rows = [{k: r.get(k) for k in wanted} for r in rows]

    headers = _column_order(rows) if not columns else [c for c in columns.split(",") if c]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"screening-{stamp}.{format}"

    if format == "json":
        return JSONResponse(
            content=rows,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    if format == "xlsx":
        return StreamingResponse(
            io.BytesIO(_rows_to_xlsx(rows, headers)),
            media_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    if format not in ("csv", "tsv"):
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")

    delimiter = "\t" if format == "tsv" else ","
    buffer = io.StringIO()
    # Headings match the table exactly, so an exported file and the screen a
    # colleague is looking at use the same words.
    writer = csv.writer(buffer, delimiter=delimiter)
    writer.writerow([label_for(h) if not raw else h for h in headers])
    for row in rows:
        writer.writerow([_flatten(row.get(h)) for h in headers])
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _flatten(value: Any) -> Any:
    """Lists and dicts have no place in a spreadsheet cell; join them readably."""
    if isinstance(value, (list, tuple)):
        return "; ".join(str(v) for v in value)
    if isinstance(value, dict):
        return "; ".join(f"{k}={v}" for k, v in value.items())
    return value


def _rows_to_xlsx(rows: list[dict[str, Any]], headers: list[str]) -> bytes:
    """Write rows to a real .xlsx workbook with a frozen, bold header row."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook(write_only=False)
    ws = wb.active
    ws.title = "Screening"
    ws.append([label_for(h) for h in headers])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    ws.freeze_panes = "A2"
    for row in rows:
        ws.append([_flatten(row.get(h)) for h in headers])
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


@router.get("/chemical/{chemical_id}")
def screening_by_chemical(chemical_id: str, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """GET /api/screening/chemical/:chemicalId — raw records, no enrichment."""
    return [s for s in all_docs(db, Screening) if s.get("chemical_id") == chemical_id]


@router.post("", status_code=201)
def add_screening(body: ScreeningIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    """POST /api/screening — must reference an existing chemical."""
    chemical = find_row(db, Chemical, "chemical_id", body.chemical_id)
    if not chemical:
        raise HTTPException(
            status_code=400,
            detail="Chemical not found. Screening data must be linked to an existing chemical.",
        )

    record = {
        "id": str(uuid.uuid4()),
        "chemical_id": body.chemical_id,
        "assay_name": body.assay_name,
        "assay_type": js_or(body.assay_type, None),
        "target": js_or(body.target, None),
        "result": body.result,
        "result_value": js_or(body.result_value, None),
        "result_unit": js_or(body.result_unit, None),
        "concentration": js_or(body.concentration, None),
        "concentration_unit": js_or(body.concentration_unit, None),
        "timepoint": js_or(body.timepoint, None),
        "replicate": js_or(body.replicate, None),
        "plate_id": js_or(body.plate_id, None),
        "well_position": js_or(body.well_position, None),
        "experiment_date": js_or(body.experiment_date, None),
        "operator": js_or(body.operator, None),
        "notes": js_or(body.notes, None),
        "metadata": js_or(body.metadata, None),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    insert_doc(db, Screening, record)
    return {"message": "Screening data added successfully", "id": record["id"]}


@router.post("/upload/excel")
async def upload_excel(
    file: Optional[UploadFile] = File(default=None), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """POST /api/screening/upload/excel.

    Two paths. If the upload matches a known laboratory template (see
    `utils/templates.py`) it is cleaned and loaded by that template's rules,
    creating any chemicals it references. Otherwise the original column-mapping
    behaviour applies unchanged, so existing uploads keep working exactly as
    before.
    """
    if file is None:
        raise HTTPException(status_code=400, detail="No file uploaded")

    content = await file.read()

    spec = detect_template(content, file.filename or "")
    if spec is not None:
        records, report = parse_with_spec(content, spec)
        return load_screening(db, records, spec, report)

    data = sheet_rows_as_dicts(content)

    inserted = 0
    errors: list[dict[str, Any]] = []
    valid_ids = {c.get("chemical_id") for c in all_docs(db, Chemical)}

    def col(row: dict[str, str], *names: str) -> Optional[str]:
        for n in names:
            v = row.get(n)
            if v not in (None, ""):
                return v
        return None

    for row in data:
        try:
            chemical_id = col(row, "chemical_id", "Chemical_ID")
            if not chemical_id or chemical_id not in valid_ids:
                errors.append({"row": col(row, "assay_name", "Assay_Name"), "error": "Chemical not found"})
                continue

            record = {
                "id": str(uuid.uuid4()),
                "chemical_id": chemical_id,
                "assay_name": col(row, "assay_name", "Assay_Name") or "Unknown Assay",
                "assay_type": col(row, "assay_type", "Assay_Type"),
                "target": col(row, "target", "Target"),
                "result": col(row, "result", "Result"),
                "result_value": col(row, "result_value", "Result_Value"),
                "result_unit": col(row, "result_unit", "Result_Unit"),
                "concentration": col(row, "concentration", "Concentration"),
                "concentration_unit": col(row, "concentration_unit", "Concentration_Unit"),
                "timepoint": col(row, "timepoint", "Timepoint"),
                "replicate": col(row, "replicate", "Replicate"),
                "plate_id": col(row, "plate_id", "Plate_ID"),
                "well_position": col(row, "well_position", "Well_Position"),
                "experiment_date": col(row, "experiment_date", "Experiment_Date"),
                "operator": col(row, "operator", "Operator"),
                "notes": col(row, "notes", "Notes"),
                "metadata": row,
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }
            insert_doc(db, Screening, record)
            inserted += 1
        except Exception as err:
            errors.append({"row": col(row, "assay_name", "Assay_Name"), "error": str(err)})

    response: dict[str, Any] = {
        "message": f"Successfully uploaded {inserted} screening records",
        "inserted": inserted,
    }
    if errors:
        response["errors"] = errors
    return response


@router.get("/{record_id}")
def get_screening(record_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """GET /api/screening/:id — one record, enriched with chemical_name."""
    row = find_row(db, Screening, "id", record_id)
    if not row:
        raise HTTPException(status_code=404, detail="Screening data not found")
    chemical = find_row(db, Chemical, "chemical_id", row.doc.get("chemical_id"))
    name = chemical.doc.get("name") if chemical else "Unknown"
    return {**row.doc, "chemical_name": name or "Unknown"}


@router.put("/{record_id}")
def update_screening(
    record_id: str,
    payload: dict[str, Any] = Body(default={}),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """PUT /api/screening/:id — merge arbitrary fields (free-form, like the v1 API)."""
    row = find_row(db, Screening, "id", record_id)
    if not row:
        raise HTTPException(status_code=404, detail="Screening data not found")
    replace_doc(db, row, {**row.doc, **payload, "updated_at": now_iso()})
    return {"message": "Screening data updated successfully"}


@router.delete("/{record_id}")
def delete_screening(record_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """DELETE /api/screening/:id."""
    row = find_row(db, Screening, "id", record_id)
    if not row:
        raise HTTPException(status_code=404, detail="Screening data not found")
    delete_row(db, row)
    return {"message": "Screening data deleted successfully"}
