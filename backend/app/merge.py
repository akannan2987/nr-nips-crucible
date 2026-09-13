"""Merge registry entries that describe one substance, without losing a row.

One home for the merge, called by the endpoint (`POST /api/chemicals/merge`)
and the terminal script (`merge_duplicate_chemicals.py`), so the browser and
the terminal merge in exactly one way.

The order matters and never changes:

1. the survivor takes any field it was missing from the entries being
   removed (nothing only the duplicate knew is lost);
2. every screening, sample and toxicology row pointing at a removed entry
   is repointed at the survivor — column and document both, because the
   document is the truth and the column its index;
3. the flags that named the removed entries (`cas_shared_with` and its
   siblings) are cleaned on every entry that carried them;
4. only then are the removed entries deleted, in one transaction.

A row is never left pointing at an entry that no longer exists (lesson 22).
The survivor records what was folded into it under `merged_entries`, so the
history is readable from the entry itself.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .compat import now_iso
from .links import linked_rows
from .models import Chemical
from .store import all_rows, find_row, replace_doc

SHARED_FLAGS = ("cas_shared_with", "dtx_shared_with", "pubchem_shared_with")
_NEVER_COPIED = {"id", "chemical_id", "created_at", "updated_at", "reviewed", "merged_entries", *SHARED_FLAGS}


class MergeError(ValueError):
    """A merge that cannot be done as asked; the message says why."""


def merge_entries(db: Session, keep_id: str, remove_ids: list[str]) -> dict[str, Any]:
    """Fold `remove_ids` into `keep_id`; returns what was kept, removed and repointed."""
    remove_ids = [r for r in dict.fromkeys(remove_ids) if r]  # unique, in order, no blanks
    if not remove_ids:
        raise MergeError("nothing to merge: 'remove' is empty")
    if keep_id in remove_ids:
        raise MergeError(f"{keep_id} cannot be both kept and removed")
    keep = find_row(db, Chemical, "chemical_id", keep_id)
    if keep is None:
        raise KeyError(keep_id)
    removed_rows = []
    for chemical_id in remove_ids:
        row = find_row(db, Chemical, "chemical_id", chemical_id)
        if row is None:
            raise KeyError(chemical_id)
        removed_rows.append(row)

    stamp = now_iso()
    keep_doc = dict(keep.doc or {})
    gone = set(remove_ids)

    # 1. anything the survivor lacks is worth carrying over
    for row in removed_rows:
        for key, value in (row.doc or {}).items():
            if key in _NEVER_COPIED:
                continue
            if keep_doc.get(key) in (None, "", [], {}):
                keep_doc[key] = value
    keep_doc["merged_entries"] = (keep_doc.get("merged_entries") or []) + [
        {
            "chemical_id": row.doc.get("chemical_id"),
            "name": row.doc.get("name"),
            "cas_number": row.doc.get("cas_number"),
            "merged_at": stamp,
        }
        for row in removed_rows
    ]

    # 2. repoint every row that pointed at a removed entry
    repointed: dict[str, int] = {}
    for label, rows in linked_rows(db, gone).items():
        for row in rows:
            doc = dict(row.doc or {})
            if doc.get("chemical_id") in gone:
                doc["chemical_id"] = keep_id
            if "chemical_ids" in doc:
                ids = [keep_id if x in gone else x for x in doc["chemical_ids"]]
                doc["chemical_ids"] = list(dict.fromkeys(ids))
            doc["updated_at"] = stamp
            row.doc = doc
            if hasattr(row, "chemical_id") and row.chemical_id in gone:
                row.chemical_id = keep_id
        repointed[label] = len(rows)
    repointed["total"] = sum(repointed.values())

    # 3. the flags that named the removed entries, on every entry still here
    for row in all_rows(db, Chemical):
        if row is keep or row in removed_rows:
            continue
        doc = row.doc or {}
        if not any(set(doc.get(flag) or []) & gone for flag in SHARED_FLAGS):
            continue
        replace_doc(db, row, _without_gone(doc, gone, stamp), commit=False)
    keep_doc = _without_gone(keep_doc, gone, stamp)
    replace_doc(db, keep, keep_doc, commit=False)

    # 4. only now, delete
    for row in removed_rows:
        db.delete(row)
    db.commit()

    return {
        "kept": keep_id,
        "removed": remove_ids,
        "rows_repointed": repointed,
        "message": f"Merged {len(remove_ids)} entr{'y' if len(remove_ids) == 1 else 'ies'} into {keep_id}; {repointed['total']} row{'' if repointed['total'] == 1 else 's'} repointed",
    }


def _without_gone(doc: dict[str, Any], gone: set[str], stamp: str) -> dict[str, Any]:
    out = dict(doc)
    for flag in SHARED_FLAGS:
        if flag in out:
            left = [x for x in (out[flag] or []) if x not in gone]
            if left:
                out[flag] = left
            else:
                out.pop(flag)
    out["updated_at"] = stamp
    return out
