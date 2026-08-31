#!/usr/bin/env python3
"""Remove chemical entries safely, without orphaning the rows that use them.

Deleting a chemical through the API or the interface removes the entry and
leaves every screening, sample and toxicology row still pointing at it. Those
rows then reference something that does not exist: they render as links leading
nowhere, and `verify-deploy.sh` reports them as dangling. This has already
happened once on production, to 1,897 rows.

This unlinks first and deletes second. Unlinked rows fall back to showing the
compound name their source file recorded, which is the honest state for a
compound whose identity is not established.

    # by identifier
    .venv/bin/python scripts/remove_chemicals.py CHEM-000123 CHEM-000456
    .venv/bin/python scripts/remove_chemicals.py CHEM-000123 --apply

    # everything registered from PubChem, to rebuild the registry from scratch
    .venv/bin/python scripts/remove_chemicals.py --pubchem-registered --apply

    # from a file, one identifier per line
    .venv/bin/python scripts/remove_chemicals.py --from-file bad-ids.txt --apply

Nothing is written without `--apply`.
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

LINKED_MODELS = (("screening", Screening), ("samples", Sample), ("toxicology", Toxicology))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ids", nargs="*", help="chemical identifiers to remove")
    parser.add_argument("--from-file", help="a file of identifiers, one per line")
    parser.add_argument(
        "--pubchem-registered",
        action="store_true",
        help="every entry created by the identification job (identification='pubchem name+cas agree')",
    )
    parser.add_argument("--apply", action="store_true", help="write changes (default: report)")
    args = parser.parse_args()

    db = SessionLocal()
    chemicals = all_rows(db, Chemical)

    wanted = set(args.ids)
    if args.from_file:
        wanted |= {
            line.strip()
            for line in Path(args.from_file).read_text().splitlines()
            if line.strip() and not line.startswith("#")
        }

    targets = [
        row
        for row in chemicals
        if row.doc.get("chemical_id") in wanted
        or (args.pubchem_registered and row.doc.get("identification") == "pubchem name+cas agree")
    ]

    if not targets:
        print("Nothing matched. Check the identifiers, or use --pubchem-registered.")
        return 1

    target_ids = {row.doc["chemical_id"] for row in targets}

    # Which rows point at them, per module.
    users: dict[str, list] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)
    for label, model in LINKED_MODELS:
        for row in all_rows(db, model):
            if row.chemical_id in target_ids:
                users[label].append(row)
                counts[label] += 1

    print(f"{len(targets)} chemical entries to remove\n")
    for row in targets[:20]:
        doc = row.doc
        print(
            f"  {doc['chemical_id']}  {str(doc.get('name'))[:38]:40} "
            f"cas={doc.get('cas_number') or '-'}"
        )
    if len(targets) > 20:
        print(f"  … and {len(targets) - 20} more")

    total = sum(counts.values())
    print(f"\n{total} rows point at them and will be unlinked:")
    for label, _ in LINKED_MODELS:
        if counts[label]:
            print(f"  {label:12} {counts[label]}")
    print("\nUnlinked rows keep the compound name their source file recorded.")

    if not args.apply:
        db.rollback()
        print("\nReport only — nothing written. Re-run with --apply.")
        return 0

    # Unlink first. If this half succeeds and the delete does not, the data is
    # still consistent: rows simply show their source names.
    for rows in users.values():
        for row in rows:
            doc = dict(row.doc)
            doc.pop("chemical_id", None)
            row.doc = doc
            row.chemical_id = None
    db.commit()

    for row in targets:
        db.delete(row)
    db.commit()

    remaining = db.query(Chemical).count()
    print(f"\nRemoved {len(targets)} entries, unlinked {total} rows. {remaining} chemicals remain.")
    print("Run ./verify-deploy.sh to confirm no dangling links were left.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
