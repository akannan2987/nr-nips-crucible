"""Alembic migration environment for the Crucible backend.

The database URL comes from the app's own config (the DATABASE_URL env var),
so the identical command works against SQLite (dev/tests) and PostgreSQL
(production):

    cd backend
    DATABASE_URL=postgresql+psycopg://user:pass@host/crucible alembic upgrade head

`prepend_sys_path = .` in alembic.ini puts backend/ on sys.path so `import app`
works from the CLI; scripts/db_bootstrap.py adds it explicitly for the app.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app import models  # noqa: F401  (registers all tables on Base.metadata)
from app.config import DATABASE_URL
from app.database import Base

# Alembic Config object (values from alembic.ini, if present).
config = context.config

# The URL always comes from the app config, overriding whatever is in the ini.
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live DB connection (`alembic upgrade --sql`)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            # Batch mode makes ALTER TABLE-style migrations work on SQLite,
            # which cannot ALTER columns in place.
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
