"""progressive subtitle batches

Revision ID: 0002_progressive_batches
Revises: 0001_initial_schema
Create Date: 2026-08-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_progressive_batches"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("videos", sa.Column("processing_status", sa.String(length=32), nullable=False, server_default="completed"))
    op.add_column("subtitles", sa.Column("batch_index", sa.Integer(), nullable=True))
    op.add_column("subtitles", sa.Column("processing_status", sa.String(length=32), nullable=False, server_default="processed"))
    op.alter_column("subtitles", "translated_text", existing_type=sa.Text(), nullable=True)
    op.create_index("ix_subtitles_batch_index", "subtitles", ["batch_index"])

    op.create_table(
        "subtitle_processing_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("video_id", sa.Integer(), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("batch_index", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Float(), nullable=False),
        sa.Column("end_time", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("video_id", "batch_index", name="uq_subtitle_batches_video_index"),
    )


def downgrade() -> None:
    op.drop_table("subtitle_processing_batches")
    op.drop_index("ix_subtitles_batch_index", table_name="subtitles")
    op.alter_column("subtitles", "translated_text", existing_type=sa.Text(), nullable=False)
    op.drop_column("subtitles", "processing_status")
    op.drop_column("subtitles", "batch_index")
    op.drop_column("videos", "processing_status")
