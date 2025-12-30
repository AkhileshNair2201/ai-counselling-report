"""add duration_seconds to transcripts

Revision ID: 0003_add_transcript_duration
Revises: 0002_create_transcripts
Create Date: 2025-01-03 00:00:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_add_transcript_duration"
down_revision = "0002_create_transcripts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transcripts", sa.Column("duration_seconds", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("transcripts", "duration_seconds")
