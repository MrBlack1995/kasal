"""add expressions column to powerbi_extraction

Revision ID: 20260812_pbi_expressions
Revises: 20260720_powerbi_extraction
Create Date: 2026-08-12

Persists the model's named/shared expressions (staging queries + parameters,
parsed alongside admin_tables by parse_admin_expressions/parse_tmdl_expressions)
so the UC Metric View Generator's DB fallback can rebuild mquery_json at full
quality (resolve_mquery_with_context needs both admin_tables AND expressions).
Existing deployed DBs are healed at startup by
_ensure_powerbi_extraction_expressions_column (src/db/session.py) with the same
column; this migration keeps the Alembic chain in sync. Idempotent on both
paths (SQLite PRAGMA check / Postgres IF NOT EXISTS here; PRAGMA check /
ADD COLUMN IF NOT EXISTS there).
"""
from alembic import op
import sqlalchemy as sa


revision = "20260812_pbi_expressions"
down_revision = "20260720_powerbi_extraction"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "powerbi_extraction" not in inspector.get_table_names():
        return  # table doesn't exist yet on this DB — nothing to alter
    existing_cols = {c["name"] for c in inspector.get_columns("powerbi_extraction")}
    if "expressions" in existing_cols:
        return  # startup self-heal already added it
    op.add_column("powerbi_extraction", sa.Column("expressions", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("powerbi_extraction", "expressions")
