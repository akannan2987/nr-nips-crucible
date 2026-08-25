#!/usr/bin/env python3
"""Merge chemical entries that describe the same substance.

Two entries can end up describing one compound when they carry different CAS
numbers that PubChem resolves to the same record — a substance and its hydrate,
for instance. The linker now prevents this, but entries created before that are
still there.

Merging keeps the **oldest** entry (the lowest identifier), repoints every
screening, sample and toxicology row at it, fills in any field the survivor was
missing from the one being removed, and only then deletes the duplicate. Rows
are never left pointing at an entry that no longer exists.

    .venv/bin/python scripts/merge_duplicate_chemicals.py            # report only
    .venv/bin/python scripts/merge_duplicate_chemicals.py --apply    # merge
"""

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("AUTO_INIT_DB", "false")

from app.database import SessionLocal  # noqa: E402
from app.models import Chemical, Sample, Screening, Toxicology  # noqa: E402
from app.store import all_rows  # noqa: E402
from app.utils.cleaning import collapse_whitespace  # noqa: E402

LINKED_MODELS = (Screening, Sample, Toxicology)


def groups_of_duplicates(rows) -> list[list]:
    """Entries that describe one substance, grouped.

    Grouped by PubChem compound id where present, and otherwise by normalised
    name. The compound id is the stronger signal: it is what makes two
    different CAS numbers recognisably the same substance.
    """
    by_cid: dict[int, list] = defaultdict(list)
    by_name: dict[str, list] = defaultdict(list)
    for row in rows:
        cid = row.doc.get("pubchem_cid")
        if cid:
            by_cid[int(cid)].append(row)
        elif row.doc.get("name"):
            by_name[collapse_whitespace(row.doc["name"]).lower()].append(row)
    found = [g for g in by_cid.values() if len(g) > 1]
    found += [g for g in by_name.values() if len(g) > 1]
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write changes (default: report)")
    args = parser.parse_args()

    db = SessionLocal()
    chemicals = all_rows(db, Chemical)
    duplicates = groups_of_duplicates(chemicals)

    if not duplicates:
        print("No duplicate chemicals found.")
        return 0

    # Which rows point at which chemical, gathered once.
    users: dict[str, list] = defaultdict(list)
    for model in LINKED_MODELS:
        for row in all_rows(db, model):
            if row.chemical_id:
                users[row.chemical_id].append(row)

    moved = removed = 0
    for group in duplicates:
        group.sort(key=lambda r: r.doc.get("chemical_id") or "")
        keep, drop = group[0], group[1:]
        keep_doc = dict(keep.doc)
        print(f"\n{keep.doc['chemical_id']}  {keep.doc.get('name')}  <- keeping")
        for row in drop:
            n = len(users.get(row.doc["chemical_id"], []))
            print(f"  {row.doc['chemical_id']}  {row.doc.get('name')}  ({n} rows point at it)")
            # Anything the survivor lacks is worth carrying over rather than
            # losing with the entry being removed.
            for key, value in row.doc.items():
                if key in ("id", "chemical_id", "created_at", "updated_at"):
                    continue
                if keep_doc.get(key) in (None, "", [], {}):
                    keep_doc[key] = value
            for user in users.get(row.doc["chemical_id"], []):
                doc = dict(user.doc)
                doc["chemical_id"] = keep_doc["chemical_id"]
                user.doc = doc
                user.chemical_id = keep_doc["chemical_id"]
                moved += 1
            removed += 1

        keep.doc = keep_doc

    print(f"\n{removed} duplicate entries would be removed, {moved} rows repointed.")
    if args.apply:
        for group in duplicates:
            for row in group[1:]:
                db.delete(row)
        db.commit()
        print("Applied.")
    else:
        db.rollback()
        print("Report only — re-run with --apply to merge.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
