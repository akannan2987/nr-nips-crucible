"""Central configuration for the Crucible Python backend.

Everything configurable comes from environment variables with sensible
defaults, so the same code runs unmodified on macOS and on the RHEL8 VM.

Key settings:
    PORT          — HTTP port (default 49160)
    DATABASE_URL  — SQLAlchemy connection string. Defaults to a SQLite file
                    at data/crucible.db.
                    Switching to PostgreSQL later is just:
                    DATABASE_URL=postgresql+psycopg://user:pass@host/dbname
"""

import os
from pathlib import Path

# Repository layout: this file lives at <repo>/backend/app/config.py
BACKEND_DIR: Path = Path(__file__).resolve().parent.parent
REPO_ROOT: Path = BACKEND_DIR.parent

# Where the React production build lives (served as static files)
CLIENT_DIST: Path = Path(os.environ.get("CLIENT_DIST", REPO_ROOT / "client" / "dist"))

# Docs directory (for the /architecture page)
DOCS_DIR: Path = Path(os.environ.get("DOCS_DIR", REPO_ROOT / "docs"))

# The SLIMS sample upload template shipped with the app
SAMPLE_TEMPLATE_PATH: Path = Path(
    os.environ.get(
        "SAMPLE_TEMPLATE_PATH",
        DOCS_DIR / "excel-templates" / "samples" / "Upload_Sample_Template.xlsx",
    )
)

# HTTP port (default 49160)
PORT: int = int(os.environ.get("PORT", "49160"))

# SQLAlchemy database URL. SQLite by default; for PostgreSQL set this env var to
# postgresql+psycopg://user:pass@host:5432/dbname
_default_sqlite = f"sqlite:///{REPO_ROOT / 'data' / 'crucible.db'}"
DATABASE_URL: str = os.environ.get("DATABASE_URL", _default_sqlite)

# When true, the app runs create_all() on startup (fine for the SQLite default
# and the test suite). Set AUTO_INIT_DB=false when Alembic owns the schema (the
# container does this and runs `alembic upgrade head` at start instead), so
# create_all never races with a migration.
AUTO_INIT_DB: bool = os.environ.get("AUTO_INIT_DB", "true").lower() == "true"

# HTTPS (env-var driven). When USE_HTTPS=true and both cert files exist,
# uvicorn serves TLS directly — no reverse proxy needed. The certs/ setup
# scripts populate these paths.
USE_HTTPS: bool = os.environ.get("USE_HTTPS", "false").lower() == "true"
SSL_CERT_PATH: Path = Path(os.environ.get("SSL_CERT_PATH", "/app/certs/server.crt"))
SSL_KEY_PATH: Path = Path(os.environ.get("SSL_KEY_PATH", "/app/certs/server.key"))

# Soft capacity targets used by the dashboard gauge (NOT enforced limits) —
# same constants as the v1 stats route.
CHEMICALS_MAX = 15000
SAMPLES_MAX = 1000
