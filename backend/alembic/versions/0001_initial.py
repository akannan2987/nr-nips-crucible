"""initial schema: chemicals, samples, screening, toxicology

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-04

Mirrors app/models.py (the hybrid document pattern: extracted lookup columns
plus a JSON/JSONB `doc` holding the full record). Kept in sync with the models
so `alembic check` reports no drift.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# JSONB on PostgreSQL, plain JSON elsewhere — mirrors app/models.py:JSONDoc.
JSON_DOC = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "chemicals",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("chemical_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.String(length=40), nullable=True),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("doc", JSON_DOC, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chemicals_chemical_id", "chemicals", ["chemical_id"], unique=True)
    op.create_index("ix_chemicals_seq", "chemicals", ["seq"], unique=False)

    op.create_table(
        "samples",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("sample_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.String(length=40), nullable=True),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("doc", JSON_DOC, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_samples_sample_id", "samples", ["sample_id"], unique=True)
    op.create_index("ix_samples_seq", "samples", ["seq"], unique=False)

    op.create_table(
        "screening",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("chemical_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.String(length=40), nullable=True),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("doc", JSON_DOC, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_screening_chemical_id", "screening", ["chemical_id"], unique=False)
    op.create_index("ix_screening_seq", "screening", ["seq"], unique=False)

    op.create_table(
        "toxicology",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("chemical_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.String(length=40), nullable=True),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("doc", JSON_DOC, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_toxicology_chemical_id", "toxicology", ["chemical_id"], unique=False)
    op.create_index("ix_toxicology_seq", "toxicology", ["seq"], unique=False)


def downgrade() -> None:
    op.drop_table("toxicology")
    op.drop_table("screening")
    op.drop_table("samples")
    op.drop_table("chemicals")
