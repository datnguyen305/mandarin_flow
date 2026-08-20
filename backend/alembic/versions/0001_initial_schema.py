"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "videos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("youtube_video_id", sa.String(length=32), nullable=False, unique=True, index=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("thumbnail_url", sa.String(length=1000), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=False, server_default="zh"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "subtitles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("video_id", sa.Integer(), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("start_time", sa.Float(), nullable=False),
        sa.Column("end_time", sa.Float(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("translated_text", sa.Text(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.UniqueConstraint("video_id", "sequence_number", name="uq_subtitles_video_sequence"),
    )
    op.create_table(
        "subtitle_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subtitle_id", sa.Integer(), sa.ForeignKey("subtitles.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("text", sa.String(length=128), nullable=False),
        sa.Column("pinyin", sa.String(length=256), nullable=True),
        sa.Column("meaning", sa.String(length=500), nullable=True),
        sa.Column("start_index", sa.Integer(), nullable=False),
        sa.Column("end_index", sa.Integer(), nullable=False),
    )
    op.create_table(
        "saved_vocabulary",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("word", sa.String(length=128), nullable=False),
        sa.Column("pinyin", sa.String(length=256), nullable=True),
        sa.Column("meaning", sa.String(length=500), nullable=True),
        sa.Column("video_id", sa.Integer(), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subtitle_id", sa.Integer(), sa.ForeignKey("subtitles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("timestamp", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("saved_vocabulary")
    op.drop_table("subtitle_tokens")
    op.drop_table("subtitles")
    op.drop_table("videos")
