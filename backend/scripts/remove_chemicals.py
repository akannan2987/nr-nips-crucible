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

    # the registry reset, step 1: unlink EVERY row from EVERY chemical,
    # keeping the chemical entries themselves
    .venv/bin/python scripts/remove_chemicals.py --unlink-all --apply

    # the registry reset, step 2: unlink every row AND remove every chemical
    .venv/bin/python scripts/remove_chemicals.py --all --apply

    # unlink the rows of particular chemicals WITHOUT removing the entries
    .venv/bin/python scripts/remove_chemicals.py CHEM-000374 --unlink-only --apply

Every mode prints how many rows of WHICH chemical are affected, most first.

Nothing is written without `--apply`. Back up first: ./container-py.sh backup

A link lives in two places on a row — the indexed `chemical_id` column and
the `chemical_id` key inside the stored document — and unlinking clears both,
because the document is the truth and the column is derived from it.
"""

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("AUTO_INIT_DB", "false")

from app.database import SessionLocal  # noqa: E402
from app.links import LINKED_MODELS, links_of, unlink_rows  # noqa: E402
from app.models import Chemical  # noqa: E402
from app.store import all_rows  # noqa: E402

# LINKED_MODELS, links_of and unlink_rows live in app/links.py since CR-6, so the
# API's forced delete and this script clear a link in exactly one way.
PUBCHEM_TAG = "pubchem name+cas agree"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ids", nargs="*", help="chemical identifiers to remove")
    parser.add_argument("--from-file", help="a file of identifiers, one per line")
    parser.add_argument(
        "--pubchem-registered",
        action="store_true",
        help=f"every entry created by the identification job (identification='{PUBCHEM_TAG}')",
    )
    parser.add_argument(
        "--unlink-all",
        action="store_true",
        help="unlink EVERY screening, sample and toxicology row from EVERY chemical; keep the chemical entries",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="unlink every row AND remove every chemical entry — the registry starts empty",
    )
    parser.add_argument(
        "--unlink-only",
        action="store_true",
        help="with identifiers / --from-file / --pubchem-registered: unlink their rows but KEEP the entries",
    )
    parser.add_argument("--apply", action="store_true", help="write changes (default: report)")
    return parser


def print_breakdown(rows_by_module: dict, chemicals: list, limit: int = 20) -> None:
    """Rows per chemical, most first, so a run says what it touched, not just how much."""
    names = {row.doc.get("chemical_id"): row.doc.get("name") for row in chemicals}
    counts: dict[str, int] = {}
    for rows in rows_by_module.values():
        for row in rows:
            for cid in links_of(row):
                counts[cid] = counts.get(cid, 0) + 1
    if not counts:
        return
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    print(f"\nrows per chemical ({len(counts)} chemicals), most first:")
    for cid, n in ranked[:limit]:
        print(f"  {n:6}  {cid:14}  {str(names.get(cid) or 'Unknown')[:50]}")
    if len(ranked) > limit:
        rest = sum(n for _, n in ranked[limit:])
        print(f"  … and {len(ranked) - limit} more chemicals ({rest} rows)")


def run(argv: list[str] | None = None, db=None) -> int:
    args = build_parser().parse_args(argv)
    own_session = db is None
    db = db or SessionLocal()
    try:
        return _run(args, db)
    finally:
        if own_session:
            db.close()


def _run(args, db) -> int:
    chemicals = all_rows(db, Chemical)

    wanted = set(args.ids)
    if args.from_file:
        wanted |= {
            line.strip()
            for line in Path(args.from_file).read_text().splitlines()
            if line.strip() and not line.startswith("#")
        }

    if args.all:
        targets = list(chemicals)
    else:
        targets = [
            row
            for row in chemicals
            if row.doc.get("chemical_id") in wanted
            or (args.pubchem_registered and row.doc.get("identification") == PUBCHEM_TAG)
        ]

    if not targets and not args.unlink_all:
        print("Nothing matched. Check the identifiers, or use --pubchem-registered, --unlink-all or --all.")
        return 1

    target_ids = {row.doc["chemical_id"] for row in targets}

    # Which rows will be unlinked, per module: every linked row for the two
    # reset modes, otherwise only the rows pointing at the targets.
    users: dict[str, list] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)
    for label, model in LINKED_MODELS:
        for row in all_rows(db, model):
            links = links_of(row)
            if links and (args.unlink_all or args.all or links & target_ids):
                users[label].append(row)
                counts[label] += 1
    total = sum(counts.values())

    if args.unlink_all and not args.all:
        print(f"REGISTRY RESET, step 1 — unlink every row; keep all {len(chemicals)} chemical entries\n")
    elif args.all:
        print(f"REGISTRY RESET, step 2 — unlink every row AND remove all {len(targets)} chemical entries\n")
    elif args.unlink_only:
        print(f"UNLINK ONLY — detach the rows of {len(targets)} chemical entries; the entries themselves are kept\n")
    else:
        print(f"{len(targets)} chemical entries to remove\n")
    if not (args.unlink_all or args.all):
        for row in targets[:20]:
            doc = row.doc
            print(
                f"  {doc['chemical_id']}  {str(doc.get('name'))[:38]:40} "
                f"cas={doc.get('cas_number') or '-'}"
            )
        if len(targets) > 20:
            print(f"  … and {len(targets) - 20} more")
        print()

    print(f"{total} rows will be unlinked:")
    for label, _ in LINKED_MODELS:
        if counts[label]:
            print(f"  {label:12} {counts[label]}")
    print_breakdown(users, chemicals)
    print("\nUnlinked rows keep the compound name their source file recorded.")

    if not args.apply:
        db.rollback()
        print("\nReport only — nothing written. Back up (./container-py.sh backup), then re-run with --apply.")
        return 0

    # Unlink first. If this half succeeds and the delete does not, the data is
    # still consistent: rows simply show their source names.
    unlinked = 0
    everything = args.unlink_all or args.all
    for rows in users.values():
        unlinked += unlink_rows(
            db, rows, apply=True, targets=None if everything else target_ids,
            progress=lambda n: print(f"  … {n} rows unlinked", flush=True),
        )

    if (args.unlink_all and not args.all) or args.unlink_only:
        print(f"\nUnlinked {unlinked} rows. All {len(chemicals)} chemical entries kept.")
        print("Run ./verify-deploy.sh to confirm no dangling links were left.")
        return 0

    for row in targets:
        db.delete(row)
    db.commit()

    remaining = db.query(Chemical).count()
    print(f"\nRemoved {len(targets)} entries, unlinked {unlinked} rows. {remaining} chemicals remain.")
    print("Run ./verify-deploy.sh to confirm no dangling links were left.")
    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
