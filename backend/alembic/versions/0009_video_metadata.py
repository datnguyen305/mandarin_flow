"""store normalized YouTube metadata

Revision ID: 0009_video_metadata
Revises: 0008_agent_requests
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_video_metadata"
down_revision = "0008_agent_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("videos", sa.Column("duration_seconds", sa.Integer(), nullable=True))
    op.add_column("videos", sa.Column("channel_name", sa.String(length=500), nullable=True))
    op.add_column("videos", sa.Column("channel_id", sa.String(length=128), nullable=True))
    op.add_column("videos", sa.Column("upload_date", sa.Date(), nullable=True))
    op.add_column("videos", sa.Column("metadata_fetched_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_videos_channel_id", "videos", ["channel_id"])


def downgrade() -> None:
    op.drop_index("ix_videos_channel_id", table_name="videos")
    op.drop_column("videos", "metadata_fetched_at")
    op.drop_column("videos", "upload_date")
    op.drop_column("videos", "channel_id")
    op.drop_column("videos", "channel_name")
    op.drop_column("videos", "duration_seconds")
