"""prevent duplicate saved words per guest

Revision ID: 0013_unique_saved_vocab_words
Revises: 0012_video_view_count
"""

from alembic import op


revision = "0013_unique_saved_vocab_words"
down_revision = "0012_video_view_count"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM saved_vocabulary duplicate
        USING saved_vocabulary keeper
        WHERE duplicate.id > keeper.id
          AND duplicate.guest_id = keeper.guest_id
          AND lower(trim(duplicate.word)) = lower(trim(keeper.word))
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_saved_vocabulary_guest_word
        ON saved_vocabulary (guest_id, lower(trim(word)))
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_saved_vocabulary_guest_word")
