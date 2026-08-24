"""store YouTube video view count

Revision ID: 0012_video_view_count
Revises: 0011_video_processing_error
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_video_view_count"
down_revision = "0011_video_processing_error"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("videos", sa.Column("view_count", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("videos", "view_count")
