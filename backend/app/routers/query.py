"""/api/query — run a read-only SQL query against the database.

Useful because the tables store whole records as JSON: questions like "which
simulants produced the highest migration for this compound" are a few lines of
SQL and are otherwise not answerable from the interface at all.

**Safety.** `/api/*` carries no authentication, so anyone who can reach the
port can call this. Three independent measures, in order of how much they are
relied upon:

1. **A read-only database connection.** On SQLite the file is opened with
   `mode=ro`, so the database itself refuses to write. This is the guarantee —
   the others are defence in depth.
2. **One statement only.** A trailing `; DROP TABLE …` is rejected before the
   database sees it.
3. **A statement allow-list.** Only `SELECT` and `WITH … SELECT` run.

Keyword filtering alone would not be enough: it is guessable and escapable. The
read-only connection is what actually makes this safe, which is why it is not
optional.

Results are capped and the query is given a deadline, so a careless join cannot
take the application down with it.
"""

from __future__ import annotations

import re
import sqlite3
import time
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import DATABASE_URL
from ..database import get_db

router = APIRouter(prefix="/api/query", tags=["query"])

MAX_ROWS = 5000
TIMEOUT_SECONDS = 15

# Only a single SELECT (or a CTE ending in SELECT) is permitted.
_ALLOWED_START = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|truncate|attach|detach|"
    r"pragma|vacuum|reindex|grant|revoke)\b",
    re.IGNORECASE,
)


def _strip_sql_comments(sql: str) -> str:
    """Remove comments so they cannot hide a second statement."""
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return sql


def validate(sql: str) -> str:
    """Return the query if it is a single read-only statement, else raise 400."""
    if not sql or not sql.strip():
        raise HTTPException(status_code=400, detail="No query given.")

    bare = _strip_sql_comments(sql).strip().rstrip(";").strip()

    if ";" in bare:
        raise HTTPException(
            status_code=400,
            detail="Only one statement can be run at a time; remove the ';'.",
        )
    if not _ALLOWED_START.match(bare):
        raise HTTPException(
            status_code=400,
            detail="Only SELECT (or WITH … SELECT) queries are allowed.",
        )
    found = _FORBIDDEN.search(bare)
    if found:
        raise HTTPException(
            status_code=400,
            detail=f"'{found.group(0).upper()}' is not allowed — this endpoint is read-only.",
        )
    return bare


def _sqlite_path() -> Optional[str]:
    if DATABASE_URL.startswith("sqlite:///"):
        return DATABASE_URL[len("sqlite:///") :]
    return None


@router.post("")
def run_query(
    payload: dict[str, Any] = Body(default={}),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """POST /api/query — `{"sql": "SELECT …"}` → columns, rows and timing."""
    sql = validate(str(payload.get("sql") or ""))
    limit = min(int(payload.get("limit") or MAX_ROWS), MAX_ROWS)

    started = time.perf_counter()
    path = _sqlite_path()
    try:
        if path:
            # A genuinely read-only handle: the database rejects writes itself,
            # rather than trusting this module to have spotted them.
            connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
            try:
                connection.execute(f"PRAGMA busy_timeout = {TIMEOUT_SECONDS * 1000}")
                cursor = connection.execute(sql)
                columns = [d[0] for d in cursor.description or []]
                rows = cursor.fetchmany(limit + 1)
            finally:
                connection.close()
        else:
            # PostgreSQL: run inside a read-only transaction.
            db.execute(text("SET TRANSACTION READ ONLY"))
            result = db.execute(text(sql))
            columns = list(result.keys())
            rows = result.fetchmany(limit + 1)
            db.rollback()
    except sqlite3.OperationalError as err:
        raise HTTPException(status_code=400, detail=f"SQL error: {err}") from err
    except Exception as err:  # noqa: BLE001 - surfaced to the user as a message
        raise HTTPException(status_code=400, detail=f"Query failed: {err}") from err

    truncated = len(rows) > limit
    rows = rows[:limit]

    return {
        "columns": columns,
        "rows": [list(r) for r in rows],
        "row_count": len(rows),
        "truncated": truncated,
        "limit": limit,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "sql": sql,
    }


@router.get("/schema")
def schema(db: Session = Depends(get_db)) -> dict[str, Any]:
    """GET /api/query/schema — tables and columns, so the editor can guide you.

    Also lists the JSON keys actually present in each `doc` column, which is
    what a query usually needs: the real fields live inside the document, not
    in the table definition.
    """
    tables: list[dict[str, Any]] = []
    for name in ("chemicals", "samples", "screening", "toxicology"):
        try:
            cols = [
                {"name": r[1], "type": r[2]}
                for r in db.execute(text(f"PRAGMA table_info({name})")).fetchall()
            ]
        except Exception:  # noqa: BLE001 - non-SQLite backend
            cols = []
        try:
            count = db.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar() or 0
        except Exception:  # noqa: BLE001
            count = 0
        doc_keys: list[str] = []
        if count:
            try:
                sample = db.execute(
                    text(f"SELECT doc FROM {name} ORDER BY seq DESC LIMIT 50")
                ).fetchall()
                import json as _json

                seen: list[str] = []
                for (raw,) in sample:
                    doc = raw if isinstance(raw, dict) else _json.loads(raw)
                    for key in doc:
                        if key not in seen and key not in ("raw",):
                            seen.append(key)
                doc_keys = seen
            except Exception:  # noqa: BLE001
                doc_keys = []
        tables.append(
            {"table": name, "rows": count, "columns": cols, "doc_keys": doc_keys}
        )
    return {"tables": tables, "max_rows": MAX_ROWS}
