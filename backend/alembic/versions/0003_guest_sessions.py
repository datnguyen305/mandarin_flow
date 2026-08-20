"""separate learning data by anonymous guest

Revision ID: 0003_guest_sessions
Revises: 0002_progressive_batches
Create Date: 2026-08-20
"""

import uuid
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_guest_sessions"
down_revision = "0002_progressive_batches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guest_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_guest_sessions_token_hash", "guest_sessions", ["token_hash"], unique=True)
    op.create_index("ix_guest_sessions_expires_at", "guest_sessions", ["expires_at"])

    legacy_guest_id = uuid.uuid4()
    guest_sessions = sa.table(
        "guest_sessions",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("token_hash", sa.String()),
        sa.column("expires_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        guest_sessions,
        [{"id": legacy_guest_id, "token_hash": f"legacy-{legacy_guest_id.hex}", "expires_at": datetime.now(UTC) + timedelta(days=36500)}],
    )

    op.add_column("saved_vocabulary", sa.Column("guest_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute(sa.text("UPDATE saved_vocabulary SET guest_id = :guest_id").bindparams(guest_id=legacy_guest_id))
    op.alter_column("saved_vocabulary", "guest_id", nullable=False)
    op.create_foreign_key(
        "fk_saved_vocabulary_guest_id", "saved_vocabulary", "guest_sessions", ["guest_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_saved_vocabulary_guest_id", "saved_vocabulary", ["guest_id"])
    op.drop_index("ix_saved_vocabulary_user_id", table_name="saved_vocabulary")
    op.drop_column("saved_vocabulary", "user_id")

    op.create_table(
        "guest_video_progress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("guest_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("guest_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("video_id", sa.Integer(), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("current_time", sa.Float(), nullable=False, server_default="0"),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_watched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("guest_id", "video_id", name="uq_guest_video_progress_guest_video"),
    )
    op.create_index("ix_guest_video_progress_guest_id", "guest_video_progress", ["guest_id"])
    op.create_index("ix_guest_video_progress_video_id", "guest_video_progress", ["video_id"])


def downgrade() -> None:
    op.add_column("saved_vocabulary", sa.Column("user_id", sa.Integer(), nullable=True))
    op.execute("UPDATE saved_vocabulary SET user_id = 1")
    op.alter_column("saved_vocabulary", "user_id", nullable=False)
    op.create_index("ix_saved_vocabulary_user_id", "saved_vocabulary", ["user_id"])
    op.drop_table("guest_video_progress")
    op.drop_index("ix_saved_vocabulary_guest_id", table_name="saved_vocabulary")
    op.drop_constraint("fk_saved_vocabulary_guest_id", "saved_vocabulary", type_="foreignkey")
    op.drop_column("saved_vocabulary", "guest_id")
    op.drop_table("guest_sessions")
