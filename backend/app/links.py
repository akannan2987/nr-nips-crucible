"""Where a link from a measurement to a chemical lives, and how to clear it.

One home for the three facts every deletion path needs (the API, the
browser through the API, and the removal script):

* a screening or toxicology row points at ONE chemical, stored twice — in the
  indexed ``chemical_id`` column and under ``chemical_id`` inside its stored
  document (the document is the truth, the column a derived index);
* a sample points at MANY, stored only in its document as a list under
  ``chemical_ids`` — there is no column (lesson 30);
* unlinking clears both places, in batches, because one transaction per row
  on a large file looks like a hang (lesson 18).

Phase CR-6 uses these to refuse a deletion while rows are linked, or — when
forced — to unlink first and delete second, always in that order.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from sqlalchemy.orm import Session

from .models import Sample, Screening, Toxicology
from .store import all_rows

LINKED_MODELS = (("screening", Screening), ("samples", Sample), ("toxicology", Toxicology))
BATCH = 5000


def links_of(row) -> set[str]:
    """The chemical identifiers a row points at, from every place a link can live."""
    doc = row.doc or {}
    ids: set[str] = set()
    if getattr(row, "chemical_id", None):
        ids.add(row.chemical_id)
    if doc.get("chemical_id"):
        ids.add(doc["chemical_id"])
    ids.update(x for x in (doc.get("chemical_ids") or []) if x)
    return ids


def linked_rows(db: Session, targets: set[str] | None) -> dict[str, list]:
    """Rows per module that point at any of `targets` (None = at anything)."""
    users: dict[str, list] = defaultdict(list)
    for label, model in LINKED_MODELS:
        for row in all_rows(db, model):
            links = links_of(row)
            if links and (targets is None or links & targets):
                users[label].append(row)
    return users


def count_links(db: Session, targets: set[str] | None) -> dict[str, int]:
    """How many rows per module point at `targets`, plus a ``total``."""
    users = linked_rows(db, targets)
    counts = {label: len(rows) for label, rows in users.items()}
    counts["total"] = sum(counts.values())
    return counts


def describe_links(counts: dict[str, int]) -> str:
    """'12 screening rows and 1 sample' — the human half of a refusal."""
    parts = []
    for label, singular in (("screening", "screening row"), ("samples", "sample"), ("toxicology", "toxicology row")):
        n = counts.get(label, 0)
        if n:
            parts.append(f"{n} {singular}{'' if n == 1 else 's'}")
    if not parts:
        return "no rows"
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def unlink_rows(
    db: Session,
    rows: list,
    apply: bool,
    targets: set[str] | None = None,
    progress: Callable[[int], None] | None = None,
) -> int:
    """Clear the link on each row — column and document — in batches. Returns rows changed.

    `targets` limits the unlinking to those identifiers; None means every link
    the row has (the reset modes). With `apply` false nothing is committed, so
    the caller can roll back a report.
    """
    changed = 0
    for row in rows:
        doc = dict(row.doc)
        if targets is None or doc.get("chemical_id") in targets:
            doc.pop("chemical_id", None)
        if "chemical_ids" in doc:
            doc["chemical_ids"] = [] if targets is None else [x for x in doc["chemical_ids"] if x not in targets]
        row.doc = doc
        if hasattr(row, "chemical_id") and (targets is None or row.chemical_id in targets):
            row.chemical_id = None
        changed += 1
        if apply and changed % BATCH == 0:
            db.commit()
            if progress:
                progress(changed)
    if apply:
        db.commit()
    return changed


def unlink_targets(db: Session, targets: set[str] | None) -> dict[str, int]:
    """Unlink every row pointing at `targets` (None = everything); returns counts per module."""
    users = linked_rows(db, targets)
    counts: dict[str, int] = {}
    for label, rows in users.items():
        counts[label] = unlink_rows(db, rows, apply=True, targets=targets)
    counts["total"] = sum(counts.values())
    return counts
