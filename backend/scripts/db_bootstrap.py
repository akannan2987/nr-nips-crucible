"""Bring the database schema to head before the app starts.

Handles three cases so the same container entrypoint works everywhere:

* Empty database (no tables)          -> ``alembic upgrade head`` (creates schema)
* Alembic-managed database            -> ``alembic upgrade head`` (applies new revisions)
* Pre-Alembic database (app tables    -> ``alembic stamp 0001_initial`` then
  exist but there is no                  ``alembic upgrade head`` (adopts the
  ``alembic_version`` table, e.g. an     existing schema without recreating it)
  older SQLite deployment built by
  ``create_all``)

Run automatically by the container entrypoint; safe to run by hand too:

    cd backend && python scripts/db_bootstrap.py
"""

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

# Make the app package importable (this file lives at <repo>/backend/scripts/).
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.database import engine  # noqa: E402

INITIAL_REVISION = "0001_initial"


def _alembic_config() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    # env.py fills sqlalchemy.url from DATABASE_URL, so nothing else is needed.
    return cfg


def main() -> int:
    cfg = _alembic_config()
    tables = set(inspect(engine).get_table_names())

    if "alembic_version" in tables:
        print("[db_bootstrap] Alembic-managed database -> upgrade head")
        command.upgrade(cfg, "head")
    elif "chemicals" in tables:
        print("[db_bootstrap] pre-Alembic schema found -> stamp initial, then upgrade head")
        command.stamp(cfg, INITIAL_REVISION)
        command.upgrade(cfg, "head")
    else:
        print("[db_bootstrap] empty database -> upgrade head (creating schema)")
        command.upgrade(cfg, "head")

    print("[db_bootstrap] schema is at head.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
