"""Central configuration for the Crucible Python backend.

Everything configurable comes from environment variables with sensible
defaults, so the same code runs unmodified on the development machine and on the RHEL8 VM.

Key settings:
    PORT          — HTTP port (default 49160)
    AUTH_MODE     — off (default) or token: the login (docs/13-authentication.md)
    CRUCIBLE_TOKEN — the shared secret of the token mode, from .env.local
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

# Which instance this process is (phases SH-12 and SH-13). container-py.sh
# passes the folder's CRUCIBLE_INSTANCE into the container; unset means the
# default instance, production. The page shows the label in its corner and
# in the tab title; an override spells it differently ("Production").
CRUCIBLE_INSTANCE: str = os.environ.get("CRUCIBLE_INSTANCE", "").strip()
CRUCIBLE_INSTANCE_LABEL: str = os.environ.get("CRUCIBLE_INSTANCE_LABEL", "").strip()

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

# ── The login (phase SH-3a; docs/13-authentication.md) ──────────────
# AUTH_MODE is the feature flag: "off" (the default; every route answers
# anyone, as every version before v2.22.0 did) or "token" (every /api route
# except health, instance and the login itself needs the shared secret).
# Later rungs add "local" and "sso". On a server the mode and the token live
# in the untracked .env.local, and container-py.sh passes them in.
AUTH_MODE: str = os.environ.get("AUTH_MODE", "off").strip().lower() or "off"
AUTH_MODES: tuple[str, ...] = ("off", "token")
# The shared secret of the token rung. Never logged, never printed, never in
# git. Generate one with: python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
CRUCIBLE_TOKEN: str = os.environ.get("CRUCIBLE_TOKEN", "").strip()
TOKEN_MIN_LENGTH: int = 32
# How long the browser stays signed in after the login page (decision A6:
# a working day).
SESSION_HOURS: int = int(os.environ.get("SESSION_HOURS", "10"))
# Cross-origin policy (decision A7): closed by default. The page is served
# by this same process, so a browser never needs another origin allowed. A
# comma-separated list reopens it for a specific other site.
CORS_ORIGINS: list[str] = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]

# Soft capacity targets used by the dashboard gauge (NOT enforced limits) —
# same constants as the v1 stats route.
CHEMICALS_MAX = 15000
SAMPLES_MAX = 1000
