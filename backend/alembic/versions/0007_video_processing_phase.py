"""add persisted video processing phase

Revision ID: 0007_processing_phase
Revises: 0006_video_tags
Create Date: 2026-08-22
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_processing_phase"
down_revision = "0006_video_tags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "videos",
        sa.Column("processing_phase", sa.String(length=32), nullable=False, server_default="pending"),
    )
    op.add_column(
        "videos",
        sa.Column("processing_progress", sa.Float(), nullable=False, server_default="0"),
    )
    op.execute(
        "UPDATE videos SET processing_phase = CASE WHEN processing_status = 'completed' "
        "THEN 'completed' ELSE processing_status END, "
        "processing_progress = CASE WHEN processing_status = 'completed' THEN 1 ELSE 0 END"
    )


def downgrade() -> None:
    op.drop_column("videos", "processing_progress")
    op.drop_column("videos", "processing_phase")
