"""Copy all records from a SQLite Crucible database into PostgreSQL.

The target schema must already exist — create it first with Alembic (or by
starting the app container once against the PostgreSQL database):

    cd backend
    DATABASE_URL=postgresql+psycopg://crucible:crucible@localhost:5432/crucible \
        alembic upgrade head

Then copy the data:

    python scripts/migrate_sqlite_to_postgres.py \
        --source sqlite:////abs/path/to/data/crucible.db \
        --target postgresql+psycopg://crucible:crucible@localhost:5432/crucible

Both URLs fall back to the SOURCE_DATABASE_URL / DATABASE_URL env vars.
Idempotent: rows whose primary key already exists in the target are skipped,
so re-running only copies what is missing. Insertion order (`seq`) is preserved.
"""

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

# Make the app package importable (this file lives at <repo>/backend/scripts/).
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.models import Chemical, Sample, Screening, Toxicology  # noqa: E402

MODELS = [Chemical, Sample, Screening, Toxicology]


def _copy_model(src: Session, dst: Session, model) -> tuple[int, int]:
    """Copy every row of ``model`` from src to dst, skipping existing ids."""
    existing_ids = set(dst.scalars(select(model.id)))
    columns = [c.key for c in inspect(model).columns]
    copied = skipped = 0
    for row in src.scalars(select(model).order_by(model.seq)):
        if row.id in existing_ids:
            skipped += 1
            continue
        dst.add(model(**{col: getattr(row, col) for col in columns}))
        copied += 1
    dst.commit()
    return copied, skipped


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy Crucible records from SQLite to PostgreSQL.",
    )
    parser.add_argument("--source", default=os.environ.get("SOURCE_DATABASE_URL"),
                        help="source SQLAlchemy URL (or SOURCE_DATABASE_URL env var)")
    parser.add_argument("--target", default=os.environ.get("DATABASE_URL"),
                        help="target SQLAlchemy URL (or DATABASE_URL env var)")
    args = parser.parse_args()

    if not args.source or not args.target:
        parser.error("both --source and --target are required "
                     "(or set SOURCE_DATABASE_URL / DATABASE_URL)")

    source_engine = create_engine(args.source)
    target_engine = create_engine(args.target)

    target_tables = set(inspect(target_engine).get_table_names())
    if "chemicals" not in target_tables:
        parser.error(
            "target has no 'chemicals' table — create the schema first with "
            "`alembic upgrade head` against the target database."
        )

    print(f"source: {args.source}")
    print(f"target: {args.target}")

    total = 0
    with Session(source_engine) as src, Session(target_engine) as dst:
        for model in MODELS:
            copied, skipped = _copy_model(src, dst, model)
            total += copied
            print(f"  {model.__tablename__:12s} copied={copied:6d}  skipped(existing)={skipped}")

    print(f"done — {total} new row(s) copied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
