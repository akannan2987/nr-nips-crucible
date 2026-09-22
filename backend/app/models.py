"""SQLAlchemy ORM models.

How the original JSON-document structure maps to SQL (the key design
decision of this port):

The v1 store kept each collection as a JSON array of loosely-shaped objects —
records gain and lose fields depending on how they were created (manual
POST, Excel upload, SDF upload), and PUT merges arbitrary keys. A fully
normalised SQL schema would silently change API response shapes, which
would break the "identical contract" requirement.

So each table follows a **hybrid document pattern**:

* `doc`     — the complete record as JSON, stored verbatim. This is what
              API responses serialise, so shapes stay byte-identical.
* extracted columns (`id`, business key, `created_at`, `seq`) — kept in
              sync with `doc` on every write, used for lookups/ordering.

`seq` preserves the original array insertion order, which some endpoints
(e.g. /api/stats/chemicals-summary) depend on. Works identically on
SQLite and PostgreSQL; a later normalisation into real columns can be
done incrementally without touching the API layer.
"""

from typing import Any

from sqlalchemy import JSON, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base

# JSONB on PostgreSQL (binary, indexable); plain JSON everywhere else (e.g.
# SQLite in tests). The stored and returned shape is identical, so the API
# contract is unchanged — this only affects how the column is stored on disk.
JSONDoc = JSON().with_variant(JSONB(), "postgresql")


class Chemical(Base):
    __tablename__ = "chemicals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # Business key used by the API (URL paths, uploads). Unique; nullable to
    # tolerate legacy records without one (SQLite/Postgres allow multiple NULLs).
    chemical_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    created_at: Mapped[str | None] = mapped_column(String(40))
    seq: Mapped[int] = mapped_column(Integer, index=True)
    doc: Mapped[dict[str, Any]] = mapped_column(JSONDoc)


class Sample(Base):
    __tablename__ = "samples"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sample_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    created_at: Mapped[str | None] = mapped_column(String(40))
    seq: Mapped[int] = mapped_column(Integer, index=True)
    doc: Mapped[dict[str, Any]] = mapped_column(JSONDoc)


class Screening(Base):
    __tablename__ = "screening"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # Screening records reference a chemical; not unique (many per chemical).
    chemical_id: Mapped[str | None] = mapped_column(String(255), index=True)
    created_at: Mapped[str | None] = mapped_column(String(40))
    seq: Mapped[int] = mapped_column(Integer, index=True)
    doc: Mapped[dict[str, Any]] = mapped_column(JSONDoc)


class Toxicology(Base):
    __tablename__ = "toxicology"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    chemical_id: Mapped[str | None] = mapped_column(String(255), index=True)
    created_at: Mapped[str | None] = mapped_column(String(40))
    seq: Mapped[int] = mapped_column(Integer, index=True)
    doc: Mapped[dict[str, Any]] = mapped_column(JSONDoc)


class User(Base):
    """A person (or a script acting for one) who may log in: rung 2 of the
    login, phase SH-3b (docs/13-authentication.md).

    The same hybrid pattern as every other table. The document holds the
    display name, the role, the enabled flag, the Argon2 password hash, the
    hash of the personal token, the login bookkeeping (last login, failed
    attempts, lock). The password itself is never stored anywhere; the hash
    can check one, never reveal it. Nothing on this table is ever returned
    by the API: /api/auth/me answers the four-field identity, the query
    console refuses this table, and the management script prints no hash.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[str | None] = mapped_column(String(40))
    seq: Mapped[int] = mapped_column(Integer, index=True)
    doc: Mapped[dict[str, Any]] = mapped_column(JSONDoc)
