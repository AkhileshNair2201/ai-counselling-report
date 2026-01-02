from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from server.models.database import Base


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audio_file_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("audio_files.id"), unique=True, index=True
    )
    text: Mapped[str] = mapped_column(Text)
    segments: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=True)
    diarized_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    diarized_segments: Mapped[list[dict[str, object]] | None] = mapped_column(
        JSON, nullable=True
    )
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
