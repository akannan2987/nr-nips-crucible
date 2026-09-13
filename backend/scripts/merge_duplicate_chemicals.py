#!/usr/bin/env python3
"""Merge chemical entries that describe the same substance.

Two entries can end up describing one compound when they carry different CAS
numbers that PubChem resolves to the same record — a substance and its hydrate,
for instance — or when a source registered one substance twice.

Merging keeps the **oldest** entry (the lowest identifier), repoints every
screening, sample and toxicology row at it, fills in any field the survivor was
missing from the one being removed, and only then deletes the duplicate. Rows
are never left pointing at an entry that no longer exists. The merge itself
lives in `app.merge` and is the same one the browser's attention page runs.

    .venv/bin/python scripts/merge_duplicate_chemicals.py                          # report only
    .venv/bin/python scripts/merge_duplicate_chemicals.py --apply                  # merge every group found
    .venv/bin/python scripts/merge_duplicate_chemicals.py CHEM-000001 CHEM-000002  # merge these into the first
    .venv/bin/python scripts/merge_duplicate_chemicals.py CHEM-000001 CHEM-000002 --apply
"""

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("AUTO_INIT_DB", "false")

from app.database import SessionLocal  # noqa: E402
from app.links import link_counts  # noqa: E402
from app.merge import MergeError, merge_entries  # noqa: E402
from app.models import Chemical  # noqa: E402
from app.store import all_rows  # noqa: E402
from app.utils.cleaning import collapse_whitespace  # noqa: E402


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ids", nargs="*", help="merge these entries into the FIRST one (default: find duplicates)")
    parser.add_argument("--apply", action="store_true", help="write changes (default: report)")
    args = parser.parse_args(argv)

    db = SessionLocal()
    counts = link_counts(db)

    if args.ids:
        if len(args.ids) < 2:
            print("Give at least two identifiers: the survivor first, then the entries to fold into it.")
            return 2
        plan = [(args.ids[0], args.ids[1:])]
    else:
        duplicates = groups_of_duplicates(all_rows(db, Chemical))
        if not duplicates:
            print("No duplicate chemicals found.")
            return 0
        plan = []
        for group in duplicates:
            group.sort(key=lambda r: r.doc.get("chemical_id") or "")
            plan.append((group[0].doc["chemical_id"], [r.doc["chemical_id"] for r in group[1:]]))

    by_id = {row.doc["chemical_id"]: row.doc for row in all_rows(db, Chemical)}
    removed = moved = 0
    for keep, drop in plan:
        print(f"\n{keep}  {by_id.get(keep, {}).get('name', '(unknown)')}  <- keeping")
        for chemical_id in drop:
            n = counts.get(chemical_id, 0)
            print(f"  {chemical_id}  {by_id.get(chemical_id, {}).get('name', '(unknown)')}  ({n} rows point at it)")
            moved += n
            removed += 1

    if not args.apply:
        print(f"\n{removed} entries would be removed, {moved} rows repointed.")
        print("Report only — re-run with --apply to merge.")
        return 0

    done_removed = done_moved = 0
    for keep, drop in plan:
        try:
            result = merge_entries(db, keep, drop)
        except (MergeError, KeyError) as err:
            print(f"  not merged ({keep}): {err}")
            continue
        done_removed += len(result["removed"])
        done_moved += result["rows_repointed"]["total"]
    print(f"\n{done_removed} entries removed, {done_moved} rows repointed. Applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
