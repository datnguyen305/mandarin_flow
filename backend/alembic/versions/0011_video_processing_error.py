"""store detailed video processing failures

Revision ID: 0011_video_processing_error
Revises: 0010_agent_request_guest
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_video_processing_error"
down_revision = "0010_agent_request_guest"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("videos", sa.Column("processing_error_code", sa.String(length=64), nullable=True))
    op.add_column("videos", sa.Column("processing_error", sa.String(length=2000), nullable=True))


def downgrade() -> None:
    op.drop_column("videos", "processing_error")
    op.drop_column("videos", "processing_error_code")
