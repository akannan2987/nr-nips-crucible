"""Loading cleaned template records into the database.

`utils/templates.py` turns a messy file into clean records. This module puts
them away — which for screening data means solving the identity problem first:
a screening result is *about* a compound, so every row needs a chemical to
point at, and in a real export most compounds are not registered yet.

Kept out of the routers (which stay thin, per the project's layering) and out
of `store.py` (which stays generic).
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from .compat import now_iso
from .models import Chemical, Screening
from .store import all_docs, insert_docs_bulk
from .utils.cleaning import collapse_whitespace, stable_hash
from .utils.templates import ParseReport, TemplateSpec


def _name_key(name: Optional[str]) -> str:
    """A forgiving key for matching compound names.

    Case and internal spacing vary between exports for what is obviously the
    same substance, so both are normalised away before comparing.
    """
    return collapse_whitespace(name).lower()


def _chemical_id_for(cas: Optional[str], name: Optional[str]) -> str:
    """A stable, readable business key for an auto-created chemical.

    CAS-keyed where possible, because a CAS number is the one identifier that
    means the same thing in every laboratory. Otherwise the name is hashed, so
    that re-importing the same file reuses the same id instead of creating
    duplicates on every upload.
    """
    if cas:
        return f"CAS-{cas}"
    return f"NAME-{stable_hash(name or 'unknown')}"


def resolve_chemicals(
    db: Session, records: list[dict[str, Any]], tag: str
) -> tuple[dict[int, str], int]:
    """Give every record a `chemical_id`, creating chemicals where needed.

    Returns `(record index → chemical_id, how many chemicals were created)`.

    Matching is by CAS number first and normalised name second, against both
    the chemicals already in the database and the ones created earlier in this
    same upload — so a compound appearing 300 times yields one chemical, not
    300.
    """
    by_cas: dict[str, str] = {}
    by_name: dict[str, str] = {}
    for doc in all_docs(db, Chemical):
        chemical_id = doc.get("chemical_id")
        if not chemical_id:
            continue
        if doc.get("cas_number"):
            by_cas.setdefault(str(doc["cas_number"]), chemical_id)
        if doc.get("name"):
            by_name.setdefault(_name_key(doc["name"]), chemical_id)

    assignments: dict[int, str] = {}
    new_docs: list[dict[str, Any]] = []

    for index, record in enumerate(records):
        cas = record.get("cas")
        name = record.get("compound_name")
        if not cas and not name:
            continue  # nothing to identify this row by; left unlinked

        chemical_id = None
        if cas and cas in by_cas:
            chemical_id = by_cas[cas]
        elif not cas and _name_key(name) in by_name:
            chemical_id = by_name[_name_key(name)]

        if chemical_id is None:
            chemical_id = _chemical_id_for(cas, name)
            timestamp = now_iso()
            new_docs.append(
                {
                    "id": str(uuid.uuid4()),
                    "chemical_id": chemical_id,
                    "name": name or "Unknown",
                    "cas_number": cas,
                    "source": {"tag": tag, "created_by": "screening import"},
                    "created_at": timestamp,
                    "updated_at": timestamp,
                }
            )
            if cas:
                by_cas[cas] = chemical_id
            if name:
                by_name.setdefault(_name_key(name), chemical_id)

        assignments[index] = chemical_id

    insert_docs_bulk(db, Chemical, new_docs)
    return assignments, len(new_docs)


def load_screening(
    db: Session, records: list[dict[str, Any]], spec: TemplateSpec, report: ParseReport
) -> dict[str, Any]:
    """Load cleaned screening records, creating their chemicals as required.

    Every record keeps the cleaned fields, its provenance `source` block (which
    carries the template's tag), and the untouched `raw` row.
    """
    assignments, chemicals_created = resolve_chemicals(db, records, spec.tag)

    timestamp = now_iso()
    docs: list[dict[str, Any]] = []
    unlinked = 0
    for index, record in enumerate(records):
        chemical_id = assignments.get(index)
        if chemical_id is None:
            unlinked += 1
        docs.append(
            {
                "id": str(uuid.uuid4()),
                "chemical_id": chemical_id,
                # `assay_name` is what the existing list/search endpoints show,
                # so it is populated from the nearest equivalent this template
                # has rather than left blank.
                "assay_name": record.get("simulant") or spec.label,
                "assay_type": record.get("analysis_type"),
                "target": record.get("migration_type"),
                **record,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        )

    inserted = insert_docs_bulk(db, Screening, docs)

    return {
        "message": (
            f"Imported {inserted} screening records from {spec.label} "
            f"({chemicals_created} new chemicals created)"
        ),
        "inserted": inserted,
        "template": spec.key,
        "tag": spec.tag,
        "chemicals_created": chemicals_created,
        "records_without_chemical": unlinked,
        "report": report.as_dict(),
    }
