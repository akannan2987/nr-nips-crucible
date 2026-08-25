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
    """Link each record to a chemical **already registered** in the application.

    This is step one of two. It matches only against chemicals that already
    exist — by CAS number first, then by name — and invents nothing. Records
    whose compound is not registered are left unlinked, and
    `scripts/link_pubchem.py` then decides whether PubChem identifies them
    confidently enough to register (step two).

    Returning `(record index -> chemical_id, chemicals created)`; the count is
    always zero here, and kept so the caller's shape does not change.
    """
    by_cas: dict[str, str] = {}
    by_name: dict[str, str] = {}
    cas_of: dict[str, str] = {}
    for doc in all_docs(db, Chemical):
        chemical_id = doc.get("chemical_id")
        if not chemical_id:
            continue
        if doc.get("cas_number"):
            cas = str(doc["cas_number"]).strip()
            by_cas.setdefault(cas, chemical_id)
            cas_of.setdefault(chemical_id, cas)
        if doc.get("name"):
            by_name.setdefault(_name_key(doc["name"]), chemical_id)

    assignments: dict[int, str] = {}
    for index, record in enumerate(records):
        # `_cas_parsed` holds the well-formed CAS numbers found in the cell;
        # the visible `cas` column keeps the cell's original text.
        for cas in record.get("_cas_parsed") or []:
            if cas in by_cas:
                assignments[index] = by_cas[cas]
                break
        else:
            name_key = _name_key(record.get("compound_name"))
            candidate = by_name.get(name_key) if name_key else None
            if candidate is None:
                continue
            # A name match is enough — unless the row's own CAS number
            # contradicts the one already recorded against that compound. Two
            # different CAS numbers under one name is a real disagreement about
            # identity, and it is the same disagreement that causes a rejection
            # against PubChem. Treating it as a match here and a rejection
            # there would apply opposite rules to identical evidence, so such a
            # row is left unlinked for a person to look at.
            row_cas = record.get("_cas_parsed") or []
            known_cas = cas_of.get(candidate)
            if row_cas and known_cas and known_cas not in row_cas:
                continue
            assignments[index] = candidate

    return assignments, 0


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
        # Fields keep the names the source uses. An earlier version mapped
        # them onto the legacy screening shape — `simulant` into `assay_name`,
        # `migration_type` into `target` — so that the fixed-column table had
        # something to show. That made the data unreadable and, worse, untrue:
        # a simulant is not an assay name. The table is now built from whatever
        # columns the records actually carry, so nothing needs renaming.
        record = {k: v for k, v in record.items() if k != "_cas_parsed"}
        docs.append(
            {
                "id": str(uuid.uuid4()),
                "chemical_id": chemical_id,
                **record,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        )

    inserted = insert_docs_bulk(db, Screening, docs)

    return {
        "message": (
            f"Imported {inserted} screening records from {spec.label}. "
            f"{inserted - unlinked} linked to registered chemicals; "
            f"{unlinked} await identification."
        ),
        "inserted": inserted,
        "template": spec.key,
        "tag": spec.tag,
        "chemicals_created": chemicals_created,
        "records_without_chemical": unlinked,
        "report": report.as_dict(),
    }
