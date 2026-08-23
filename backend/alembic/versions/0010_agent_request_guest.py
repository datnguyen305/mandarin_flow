"""associate chatbot video requests with guest sessions

Revision ID: 0010_agent_request_guest
Revises: 0009_video_metadata
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_agent_request_guest"
down_revision = "0009_video_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_requests", sa.Column("guest_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_agent_requests_guest_id_guest_sessions",
        "agent_requests",
        "guest_sessions",
        ["guest_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_agent_requests_guest_id", "agent_requests", ["guest_id"])
    op.create_index("ix_agent_requests_guest_type", "agent_requests", ["guest_id", "type"])


def downgrade() -> None:
    op.drop_index("ix_agent_requests_guest_type", table_name="agent_requests")
    op.drop_index("ix_agent_requests_guest_id", table_name="agent_requests")
    op.drop_constraint("fk_agent_requests_guest_id_guest_sessions", "agent_requests", type_="foreignkey")
    op.drop_column("agent_requests", "guest_id")
