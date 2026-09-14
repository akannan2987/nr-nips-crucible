#!/usr/bin/env python3
"""The counts above the registry table, and the entries behind a tag, from the terminal.

The same numbers the Chemical Registry page shows in its strip and chips
(phase CR-11) and the API answers at `GET /api/chemicals/summary`: how many
compounds, how many with one batch and how many with several, how many
batch rows, and how many entries carry each source tag. All three call
`app.tags`, so they cannot disagree.

    .venv/bin/python scripts/registry_summary.py                              # the counts
    .venv/bin/python scripts/registry_summary.py --batches several            # list the compounds with several batches
    .venv/bin/python scripts/registry_summary.py --tag "SDF upload"           # list the entries carrying a tag
    .venv/bin/python scripts/registry_summary.py --tag "Excel upload" --tag "SDF upload"        # carrying BOTH
    .venv/bin/python scripts/registry_summary.py --tag "Excel upload" --tag "SDF upload" --any  # carrying EITHER
    .venv/bin/python scripts/registry_summary.py --json                       # the endpoint's answer

Report only: this script never writes.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("AUTO_INIT_DB", "false")

from app.database import SessionLocal  # noqa: E402
from app.models import Chemical  # noqa: E402
from app.store import all_docs  # noqa: E402
from app.tags import TAGS, batch_count, filter_batches, filter_tags, registry_summary, tags_of  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tag", action="append", default=[], help="list entries carrying this tag (repeatable)")
    parser.add_argument("--any", action="store_true", help="with several --tag: entries carrying ANY of them (default: all)")
    parser.add_argument("--batches", choices=["one", "several"], help="list entries with one batch, or with several")
    parser.add_argument("--json", action="store_true", help="print the summary as JSON (what GET /api/chemicals/summary answers)")
    parser.add_argument("--limit", type=int, default=50, help="how many entries to list (default 50)")
    args = parser.parse_args(argv)

    db = SessionLocal()
    summary = registry_summary(db)
    if args.json:
        print(json.dumps(summary, indent=2))
        return 0

    print(f"{summary['total']} compounds: {summary['one_batch']} with one batch, {summary['several_batches']} with several;"
          f" {summary['batch_rows']} batch rows.")
    print("Entries per tag:")
    for tag in TAGS:
        print(f"  {summary['tags'][tag]:>7}  {tag}")

    if args.tag or args.batches:
        docs = [{**d, "tags": tags_of(d)} for d in all_docs(db, Chemical)]
        docs = filter_batches(docs, args.batches)
        docs = filter_tags(docs, args.tag, "any" if args.any else "all")
        what = []
        if args.batches:
            what.append(f"{args.batches} batch{'es' if args.batches == 'several' else ''}")
        if args.tag:
            what.append((" or " if args.any else " and ").join(args.tag))
        print(f"\n{len(docs)} entr{'y' if len(docs) == 1 else 'ies'} with {', '.join(what)}:")
        for d in docs[: args.limit]:
            print(f"  {d['chemical_id']}  {str(d.get('name'))[:44]:<44}  batches={batch_count(d)}  {', '.join(d['tags'])}")
        if len(docs) > args.limit:
            print(f"  … and {len(docs) - args.limit} more (--limit to see them)")
    print("\nThe same counts, with buttons: the strip above the Chemical Registry table in the browser.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
