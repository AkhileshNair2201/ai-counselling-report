"""create transcripts table

Revision ID: 0002_create_transcripts
Revises: 0001_create_audio_files
Create Date: 2025-01-02 00:00:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_create_transcripts"
down_revision = "0001_create_audio_files"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transcripts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("audio_file_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("segments", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["audio_file_id"], ["audio_files.id"]),
    )
    op.create_index(
        "ix_transcripts_audio_file_id", "transcripts", ["audio_file_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_transcripts_audio_file_id", table_name="transcripts")
    op.drop_table("transcripts")
