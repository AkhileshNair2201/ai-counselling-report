"""add audio_chunks and chunk_transcripts tables

Revision ID: 0006_add_audio_chunks
Revises: 0005_create_sessions_and_notes
Create Date: 2025-01-06 00:00:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0006_add_audio_chunks"
down_revision = "0005_create_sessions_and_notes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "audio_chunks" not in existing_tables:
        op.create_table(
            "audio_chunks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("audio_file_id", sa.Integer(), nullable=False),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("file_path", sa.String(length=512), nullable=False),
            sa.Column("start_seconds", sa.Float(), nullable=True),
            sa.Column("end_seconds", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["audio_file_id"], ["audio_files.id"]),
        )
        op.create_index(
            "ix_audio_chunks_audio_file_id", "audio_chunks", ["audio_file_id"]
        )

    if "chunk_transcripts" not in existing_tables:
        op.create_table(
            "chunk_transcripts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("audio_chunk_id", sa.Integer(), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("segments", sa.JSON(), nullable=True),
            sa.Column("diarized_text", sa.Text(), nullable=True),
            sa.Column("diarized_segments", sa.JSON(), nullable=True),
            sa.Column("duration_seconds", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["audio_chunk_id"], ["audio_chunks.id"]),
        )
        op.create_index(
            "ix_chunk_transcripts_audio_chunk_id",
            "chunk_transcripts",
            ["audio_chunk_id"],
            unique=True,
        )


def downgrade() -> None:
    op.drop_index(
        "ix_chunk_transcripts_audio_chunk_id", table_name="chunk_transcripts"
    )
    op.drop_table("chunk_transcripts")
    op.drop_index("ix_audio_chunks_audio_file_id", table_name="audio_chunks")
    op.drop_table("audio_chunks")
