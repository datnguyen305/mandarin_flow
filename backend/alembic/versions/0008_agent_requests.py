"""add human approval requests for agent actions

Revision ID: 0008_agent_requests
Revises: 0007_processing_phase
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0008_agent_requests"
down_revision = "0007_processing_phase"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_requests",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=False, server_default="agent"),
        sa.Column("approved_by", sa.String(length=128), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_requests_type_status", "agent_requests", ["type", "status"])
    op.create_index("ix_agent_requests_expires_at", "agent_requests", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_requests_expires_at", table_name="agent_requests")
    op.drop_index("ix_agent_requests_type_status", table_name="agent_requests")
    op.drop_table("agent_requests")
