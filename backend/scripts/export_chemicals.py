#!/usr/bin/env python3
"""Write every registry entry to a JSON file that import_file.py can load back.

    ./container-py.sh script export_chemicals.py -o /app/data/registry-export.json
    ./container-py.sh export chemicals ~/registry-export.json        # runs this, then copies the file out

The default database is the running one. To read a *backup* instead — the
review loop of decision D10: export the old entries, review them, load the
good ones — point --db at a copy of the backup placed under data/ (which is
mounted into the container):

    cp ~/data-backup-20260908-before-R2.db data/review-source.db
    ./container-py.sh script export_chemicals.py --db sqlite:////app/data/review-source.db -o /app/data/registry-review.json

The output is a JSON list of records with the API's field names, sorted by
identifier; the file lands under data/ on the host, which git ignores.

`run(argv, db)` exists so the tests can drive it against a throwaway database.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.imports import export_chemicals  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-o", "--out", required=True, help="where to write the JSON file")
    parser.add_argument("--db", default=None, help="a SQLAlchemy URL to read instead of the running database, e.g. sqlite:////app/data/review-source.db")
    return parser


def _session(url: str | None):
    if url is None:
        from app.database import SessionLocal
        return SessionLocal()
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    return sessionmaker(bind=create_engine(url))()


def run(argv: list[str] | None = None, db=None) -> int:
    args = build_parser().parse_args(argv)
    own = db is None
    if own:
        db = _session(args.db)
    try:
        records = export_chemicals(db)
    finally:
        if own:
            db.close()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(records)} chemicals to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
