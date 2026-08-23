"""store validated normalized dictionary entries

Revision ID: 0005_normalized_dictionary
Revises: 0004_dictionary_enrichment_cache
Create Date: 2026-08-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0005_normalized_dictionary"
down_revision = "0004_dictionary_enrichment_cache"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "normalized_dictionary_entries",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("simplified", sa.String(length=128), nullable=False),
        sa.Column("traditional", sa.String(length=128), nullable=False),
        sa.Column("entry_type", sa.String(length=32), nullable=False),
        sa.Column("readings_json", postgresql.JSONB(), nullable=False),
        sa.Column("references_json", postgresql.JSONB(), nullable=False),
        sa.Column("hsk_level", sa.SmallInteger(), nullable=True),
        sa.Column("source_name", sa.String(length=32), nullable=False, server_default="cvdict"),
        sa.Column("source_raw_json", postgresql.JSONB(), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("normalized_json", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("validation_issues", postgresql.JSONB(), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for column in ("simplified", "traditional", "entry_type", "hsk_level", "source_hash", "status"):
        op.create_index(f"ix_normalized_dictionary_entries_{column}", "normalized_dictionary_entries", [column])


def downgrade() -> None:
    op.drop_table("normalized_dictionary_entries")
