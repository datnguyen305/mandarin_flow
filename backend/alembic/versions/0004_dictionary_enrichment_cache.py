"""persist dictionary enrichment cache

Revision ID: 0004_dictionary_enrichment_cache
Revises: 0003_guest_sessions
Create Date: 2026-08-20
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_dictionary_enrichment_cache"
down_revision = "0003_guest_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dictionary_enrichment_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("word", sa.String(length=128), nullable=False),
        sa.Column("context_hash", sa.String(length=64), nullable=False),
        sa.Column("context", sa.String(length=4000), nullable=False),
        sa.Column("source_language", sa.String(length=16), nullable=False),
        sa.Column("target_language", sa.String(length=16), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("enrichment_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "word",
            "context_hash",
            "source_language",
            "target_language",
            name="uq_dictionary_enrichment_lookup",
        ),
    )
    op.create_index("ix_dictionary_enrichment_cache_word", "dictionary_enrichment_cache", ["word"])
    op.create_index("ix_dictionary_enrichment_cache_context_hash", "dictionary_enrichment_cache", ["context_hash"])


def downgrade() -> None:
    op.drop_index("ix_dictionary_enrichment_cache_context_hash", table_name="dictionary_enrichment_cache")
    op.drop_index("ix_dictionary_enrichment_cache_word", table_name="dictionary_enrichment_cache")
    op.drop_table("dictionary_enrichment_cache")
