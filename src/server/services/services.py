from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select

from server.models.audio import AudioFile
from server.models.transcript import Transcript
from server.models.database import SessionLocal
from server.agents.diarization_agent import DiarizationAgent
from server.agents.transcription_agent import TranscriptionAgent

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
ALLOWED_CONTENT_TYPES = {
    "audio/mpeg",
    "audio/mp4",
    "audio/wav",
    "audio/x-wav",
    "audio/flac",
    "audio/aac",
    "audio/ogg",
    "audio/webm",
}


async def save_audio(file: UploadFile) -> dict[str, str]:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported audio type")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "audio").suffix
    file_key = uuid4().hex
    safe_name = f"{file_key}{suffix}"
    destination = UPLOAD_DIR / safe_name

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty file")

    with SessionLocal() as session:
        audio = AudioFile(
            file_key=file_key,
            original_filename=file.filename or "audio",
            content_type=file.content_type or "",
        )
        session.add(audio)
        session.commit()

    destination.write_bytes(contents)

    return {
        "filename": safe_name,
        "file_key": file_key,
        "path": str(destination.relative_to(Path.cwd())),
        "content_type": file.content_type or "",
    }


def _resolve_audio_path(file_key: str) -> Path:
    matching = next(UPLOAD_DIR.glob(f"{file_key}*"), None)
    if matching is None:
        raise HTTPException(status_code=404, detail="Audio file not found on disk")
    return matching


def _calculate_duration_seconds(segments: list[dict[str, object]]) -> float | None:
    if not segments:
        return None
    max_end = None
    for segment in segments:
        timestamp = segment.get("timestamp") if isinstance(segment, dict) else None
        end_value = None
        if isinstance(timestamp, dict):
            end_value = timestamp.get("end")
        if isinstance(end_value, (int, float)):
            max_end = end_value if max_end is None else max(max_end, end_value)
    return float(max_end) if max_end is not None else None


def transcribe_audio(file_key: str) -> dict[str, object]:
    with SessionLocal() as session:
        result = session.execute(
            select(AudioFile).where(AudioFile.file_key == file_key)
        ).scalar_one_or_none()
        if result is None:
            raise HTTPException(status_code=404, detail="Audio file not found")

    audio_path = _resolve_audio_path(file_key)
    try:
        agent = TranscriptionAgent.from_env()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    transcript_payload = agent.transcribe(audio_path)
    transcript_text = str(transcript_payload.get("text", ""))
    segments = transcript_payload.get("segments", [])
    duration_seconds = (
        _calculate_duration_seconds(segments)
        if isinstance(segments, list)
        else None
    )

    with SessionLocal() as session:
        existing = session.execute(
            select(Transcript).where(Transcript.audio_file_id == result.id)
        ).scalar_one_or_none()
        if existing is None:
            record = Transcript(
                audio_file_id=result.id,
                text=transcript_text,
                segments=segments,
                duration_seconds=duration_seconds,
            )
            session.add(record)
        else:
            existing.text = transcript_text
            existing.segments = segments
            existing.duration_seconds = duration_seconds
            existing.updated_at = datetime.utcnow()

        session.commit()

        stored = session.execute(
            select(Transcript).where(Transcript.audio_file_id == result.id)
        ).scalar_one()

    return {
        "file_key": file_key,
        "text": stored.text,
        "segments": stored.segments or [],
    }


def list_transcripts(page: int, page_size: int) -> dict[str, object]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    offset_value = (page - 1) * page_size

    with SessionLocal() as session:
        total = session.execute(select(func.count()).select_from(Transcript)).scalar_one()
        rows = session.execute(
            select(AudioFile, Transcript)
            .join(Transcript, Transcript.audio_file_id == AudioFile.id)
            .order_by(AudioFile.created_at.desc())
            .offset(offset_value)
            .limit(page_size)
        ).all()

    items = []
    for audio, transcript in rows:
        duration = transcript.duration_seconds
        if duration is None and transcript.segments:
            duration = _calculate_duration_seconds(transcript.segments)
        items.append(
            {
                "file_key": audio.file_key,
                "original_filename": audio.original_filename,
                "content_type": audio.content_type,
                "duration_seconds": duration,
                "transcript_available": True,
                "diarization_available": bool(transcript.diarized_segments),
            }
        )

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": items,
    }


def get_transcript_segments(file_key: str) -> dict[str, object]:
    with SessionLocal() as session:
        row = session.execute(
            select(AudioFile, Transcript)
            .join(Transcript, Transcript.audio_file_id == AudioFile.id)
            .where(AudioFile.file_key == file_key)
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Transcript not found")
        audio, transcript = row

    return {
        "file_key": audio.file_key,
        "text": transcript.text,
        "segments": transcript.segments or [],
    }


def diarize_audio(file_key: str) -> dict[str, object]:
    with SessionLocal() as session:
        result = session.execute(
            select(AudioFile).where(AudioFile.file_key == file_key)
        ).scalar_one_or_none()
        if result is None:
            raise HTTPException(status_code=404, detail="Audio file not found")

    audio_path = _resolve_audio_path(file_key)
    try:
        agent = DiarizationAgent.from_env()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    diarization_payload = agent.diarize(audio_path, result.content_type)
    diarized_text = str(diarization_payload.get("text", ""))
    diarized_segments = diarization_payload.get("segments", [])
    duration_seconds = (
        _calculate_duration_seconds(diarized_segments)
        if isinstance(diarized_segments, list)
        else None
    )

    with SessionLocal() as session:
        existing = session.execute(
            select(Transcript).where(Transcript.audio_file_id == result.id)
        ).scalar_one_or_none()
        if existing is None:
            record = Transcript(
                audio_file_id=result.id,
                text=diarized_text,
                segments=diarized_segments,
                diarized_text=diarized_text,
                diarized_segments=diarized_segments,
                duration_seconds=duration_seconds,
            )
            session.add(record)
        else:
            existing.diarized_text = diarized_text
            existing.diarized_segments = diarized_segments
            existing.segments = diarized_segments
            if not existing.text:
                existing.text = diarized_text
            existing.duration_seconds = duration_seconds
            existing.updated_at = datetime.utcnow()

        session.commit()

        stored = session.execute(
            select(Transcript).where(Transcript.audio_file_id == result.id)
        ).scalar_one()

    return {
        "file_key": file_key,
        "text": stored.diarized_text or "",
        "segments": stored.diarized_segments or [],
    }
