"""the users table: local accounts, rung 2 of the login (phase SH-3b)

Revision ID: 0002_users
Revises: 0001_initial
Create Date: 2026-09-23

Mirrors app/models.py:User (the hybrid document pattern: the indexed
username beside a JSON/JSONB `doc` holding the display name, role, enabled
flag, the Argon2 password hash and the hash of the personal token). Kept in
sync with the model so `alembic check` reports no drift. An existing
database gains an empty table; nothing else changes, and downgrading drops
it again.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_users"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# JSONB on PostgreSQL, plain JSON elsewhere — mirrors app/models.py:JSONDoc.
JSON_DOC = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.String(length=40), nullable=True),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("doc", JSON_DOC, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_seq", "users", ["seq"], unique=False)


def downgrade() -> None:
    op.drop_table("users")
