#!/usr/bin/env python3
"""Import a chemicals file into the registry from the terminal — the same door the upload page uses.

    ./container-py.sh script import_file.py chemicals /app/data/imports/registry-review.json
    ./container-py.sh import chemicals ~/registry-review.json        # copies the file in, then runs this

Formats: .json (the API's field names, or {"chemicals": [...]} — what
export_chemicals.py writes), .csv, .tsv, .xlsx, .xls, .sdf. Every route
upserts by chemical_id and prints the same report the API answers with.
Only the chemicals module is supported here; screening files arrive by the
upload endpoint until phase SD-2, and samples until SM-2.

`run(argv, db)` exists so the tests can drive it against a throwaway database.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.imports import ImportError_, import_chemicals_file  # noqa: E402

MODULES = ("chemicals",)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("module", choices=MODULES, help="which registry the file is for (chemicals)")
    parser.add_argument("path", help="the file: .json, .csv, .tsv, .xlsx, .xls or .sdf")
    parser.add_argument("--json", action="store_true", help="print the report as JSON instead of prose")
    return parser


def run(argv: list[str] | None = None, db=None) -> int:
    args = build_parser().parse_args(argv)
    path = Path(args.path)
    if not path.is_file():
        print(f"No such file: {path}", file=sys.stderr)
        return 2
    content = path.read_bytes()
    own = db is None
    if own:
        db = SessionLocal()
    try:
        report = import_chemicals_file(db, path.name, content)
    except ImportError_ as err:
        print(f"Refused: {err}", file=sys.stderr)
        return 1
    finally:
        if own:
            db.close()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(report["message"])
        for e in report.get("errors") or []:
            print(f"  ! {e.get('row') or e.get('molecule')}: {e.get('error')}")
        if report.get("errors"):
            print(f"{len(report['errors'])} record(s) skipped; the rest were written.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
