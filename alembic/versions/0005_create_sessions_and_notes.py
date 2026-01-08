"""create sessions and session_notes tables, link audio_files to sessions

Revision ID: 0005_create_sessions_and_notes
Revises: 0004_add_diarization_fields
Create Date: 2025-01-05 00:00:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_create_sessions_and_notes"
down_revision = "0004_add_diarization_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("session_date", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "session_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("note_markdown", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("key_points", sa.JSON(), nullable=True),
        sa.Column("action_items", sa.JSON(), nullable=True),
        sa.Column("risk_flags", sa.JSON(), nullable=True),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
    )
    op.create_index(
        "ix_session_notes_session_id", "session_notes", ["session_id"], unique=True
    )
    op.add_column("audio_files", sa.Column("session_id", sa.Integer(), nullable=True))
    op.create_index(
        "ix_audio_files_session_id", "audio_files", ["session_id"], unique=False
    )
    op.create_foreign_key(
        "fk_audio_files_session_id", "audio_files", "sessions", ["session_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_audio_files_session_id", "audio_files", type_="foreignkey")
    op.drop_index("ix_audio_files_session_id", table_name="audio_files")
    op.drop_column("audio_files", "session_id")
    op.drop_index("ix_session_notes_session_id", table_name="session_notes")
    op.drop_table("session_notes")
    op.drop_table("sessions")
