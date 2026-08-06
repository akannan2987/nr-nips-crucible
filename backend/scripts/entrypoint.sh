#!/bin/sh
# Container entrypoint: bring the database schema to head (Alembic), then serve.
#
# Runs `alembic upgrade head` (or adopts a pre-Alembic schema) via
# db_bootstrap.py, then execs uvicorn. Keeping migrations here means a fresh
# PostgreSQL database is provisioned automatically on first start.
set -e
cd /app/backend
python scripts/db_bootstrap.py
exec python -m app.main
