"""add diarization fields to transcripts

Revision ID: 0004_add_diarization_fields
Revises: 0003_add_transcript_duration
Create Date: 2025-01-04 00:00:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_add_diarization_fields"
down_revision = "0003_add_transcript_duration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transcripts", sa.Column("diarized_text", sa.Text(), nullable=True))
    op.add_column(
        "transcripts", sa.Column("diarized_segments", sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("transcripts", "diarized_segments")
    op.drop_column("transcripts", "diarized_text")
