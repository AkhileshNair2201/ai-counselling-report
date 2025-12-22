"""create audio_files table

Revision ID: 0001_create_audio_files
Revises: 
Create Date: 2025-01-01 00:00:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_create_audio_files"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audio_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("file_key", sa.String(length=64), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_audio_files_file_key", "audio_files", ["file_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_audio_files_file_key", table_name="audio_files")
    op.drop_table("audio_files")
