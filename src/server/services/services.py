from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select

from server.models.audio import AudioFile
from server.models.session import Session
from server.models.session_note import SessionNote
from server.models.transcript import Transcript
from server.models.database import SessionLocal
from server.agents.diarization_agent import DiarizationAgent
from server.agents.notes_agent import NotesAgent
from server.agents.transcription_agent import TranscriptionAgent
from server.services.vector_store import upsert_session_note_vector, upsert_transcript_vector
from server.core.celery_app import celery_app

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


async def save_session_audio(file: UploadFile) -> dict[str, object]:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported audio type")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "session").suffix
    file_key = uuid4().hex
    safe_name = f"{file_key}{suffix}"
    destination = UPLOAD_DIR / safe_name

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty file")

    title = file.filename or "Counseling Session"

    with SessionLocal() as session:
        session_row = Session(title=title, status="uploaded")
        session.add(session_row)
        session.flush()
        session_id = session_row.id
        audio = AudioFile(
            session_id=session_id,
            file_key=file_key,
            original_filename=title,
            content_type=file.content_type or "",
        )
        session.add(audio)
        session.commit()

    destination.write_bytes(contents)

    return {
        "session_id": session_id,
        "filename": safe_name,
        "file_key": file_key,
        "path": str(destination.relative_to(Path.cwd())),
        "content_type": file.content_type or "",
        "title": title,
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


def _index_transcript(
    *,
    transcript_id: int,
    file_key: str,
    text: str,
    segments: list[dict[str, object]] | None,
    diarized: bool,
) -> None:
    try:
        upsert_transcript_vector(
            transcript_id=transcript_id,
            file_key=file_key,
            text=text,
            segments=segments,
            diarized=diarized,
        )
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Vector indexing failed: {exc}",
        ) from exc


def _index_session_note(
    *,
    session_id: int,
    note_markdown: str,
    summary: str | None,
    version: str,
) -> None:
    try:
        upsert_session_note_vector(
            session_id=session_id,
            note_markdown=note_markdown,
            summary=summary,
            version=version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Vector indexing failed: {exc}",
        ) from exc


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


def transcribe_session(session_id: int) -> dict[str, object]:
    with SessionLocal() as session:
        row = session.execute(
            select(Session, AudioFile).join(
                AudioFile, AudioFile.session_id == Session.id
            ).where(Session.id == session_id)
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Session not found")
        session_row, audio = row

    audio_path = _resolve_audio_path(audio.file_key)
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
            select(Transcript).where(Transcript.audio_file_id == audio.id)
        ).scalar_one_or_none()
        if existing is None:
            record = Transcript(
                audio_file_id=audio.id,
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

        session_row = session.get(Session, session_id)
        if session_row:
            session_row.status = "transcribed"
            session_row.updated_at = datetime.utcnow()
        session.commit()

        stored = session.execute(
            select(Transcript).where(Transcript.audio_file_id == audio.id)
        ).scalar_one()

    return {
        "session_id": session_id,
        "file_key": audio.file_key,
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


def list_sessions(page: int, page_size: int) -> dict[str, object]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    offset_value = (page - 1) * page_size

    with SessionLocal() as session:
        total = session.execute(select(func.count()).select_from(Session)).scalar_one()
        rows = session.execute(
            select(Session, AudioFile, Transcript, SessionNote)
            .join(AudioFile, AudioFile.session_id == Session.id)
            .outerjoin(Transcript, Transcript.audio_file_id == AudioFile.id)
            .outerjoin(SessionNote, SessionNote.session_id == Session.id)
            .order_by(Session.created_at.desc())
            .offset(offset_value)
            .limit(page_size)
        ).all()

    items = []
    for session_row, audio, transcript, note in rows:
        duration = transcript.duration_seconds if transcript else None
        if duration is None and transcript and transcript.segments:
            duration = _calculate_duration_seconds(transcript.segments)
        items.append(
            {
                "session_id": session_row.id,
                "title": session_row.title,
                "status": session_row.status,
                "session_date": session_row.session_date.isoformat()
                if session_row.session_date
                else None,
                "file_key": audio.file_key,
                "content_type": audio.content_type,
                "duration_seconds": duration,
                "transcript_available": bool(transcript),
                "notes_available": bool(note),
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


def get_session_detail(session_id: int) -> dict[str, object]:
    with SessionLocal() as session:
        row = session.execute(
            select(Session, AudioFile, Transcript)
            .join(AudioFile, AudioFile.session_id == Session.id)
            .outerjoin(Transcript, Transcript.audio_file_id == AudioFile.id)
            .where(Session.id == session_id)
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Session not found")
        session_row, audio, transcript = row

    return {
        "session_id": session_row.id,
        "title": session_row.title,
        "status": session_row.status,
        "session_date": session_row.session_date.isoformat()
        if session_row.session_date
        else None,
        "file_key": audio.file_key,
        "content_type": audio.content_type,
        "transcript_available": bool(transcript),
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


def diarize_session(session_id: int) -> dict[str, object]:
    with SessionLocal() as session:
        row = session.execute(
            select(Session, AudioFile).join(
                AudioFile, AudioFile.session_id == Session.id
            ).where(Session.id == session_id)
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Session not found")
        session_row, audio = row

    audio_path = _resolve_audio_path(audio.file_key)
    try:
        agent = DiarizationAgent.from_env()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    diarization_payload = agent.diarize(audio_path, audio.content_type)
    diarized_text = str(diarization_payload.get("text", ""))
    diarized_segments = diarization_payload.get("segments", [])
    duration_seconds = (
        _calculate_duration_seconds(diarized_segments)
        if isinstance(diarized_segments, list)
        else None
    )

    with SessionLocal() as session:
        existing = session.execute(
            select(Transcript).where(Transcript.audio_file_id == audio.id)
        ).scalar_one_or_none()
        if existing is None:
            record = Transcript(
                audio_file_id=audio.id,
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

        session_row = session.get(Session, session_id)
        if session_row:
            session_row.status = "transcribed"
            session_row.updated_at = datetime.utcnow()
        session.commit()

        stored = session.execute(
            select(Transcript).where(Transcript.audio_file_id == audio.id)
        ).scalar_one()

    return {
        "session_id": session_id,
        "file_key": audio.file_key,
        "text": stored.diarized_text or "",
        "segments": stored.diarized_segments or [],
    }


def generate_session_notes(session_id: int) -> dict[str, object]:
    with SessionLocal() as session:
        row = session.execute(
            select(Session, AudioFile, Transcript)
            .join(AudioFile, AudioFile.session_id == Session.id)
            .outerjoin(Transcript, Transcript.audio_file_id == AudioFile.id)
            .where(Session.id == session_id)
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Session not found")
        session_row, audio, transcript = row
        if transcript is None:
            raise HTTPException(status_code=400, detail="Transcript not available")

    diarized_segments = transcript.diarized_segments or transcript.segments
    text_for_notes = transcript.diarized_text or transcript.text or ""
    try:
        agent = NotesAgent.from_env()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    note_payload = agent.generate_notes(
        transcript_text=text_for_notes,
        diarized_segments=diarized_segments,
    )

    with SessionLocal() as session:
        existing = session.execute(
            select(SessionNote).where(SessionNote.session_id == session_id)
        ).scalar_one_or_none()
        if existing is None:
            record = SessionNote(
                session_id=session_id,
                note_markdown=note_payload["note_markdown"],
                summary=note_payload["summary"],
                key_points=note_payload["key_points"],
                action_items=note_payload["action_items"],
                risk_flags=note_payload["risk_flags"],
                model=note_payload["model"],
                version=note_payload["version"],
            )
            session.add(record)
        else:
            existing.note_markdown = note_payload["note_markdown"]
            existing.summary = note_payload["summary"]
            existing.key_points = note_payload["key_points"]
            existing.action_items = note_payload["action_items"]
            existing.risk_flags = note_payload["risk_flags"]
            existing.model = note_payload["model"]
            existing.version = note_payload["version"]
            existing.updated_at = datetime.utcnow()

        session_row = session.get(Session, session_id)
        if session_row:
            session_row.status = "noted"
            session_row.updated_at = datetime.utcnow()
        session.commit()

        stored = session.execute(
            select(SessionNote).where(SessionNote.session_id == session_id)
        ).scalar_one()

    _index_session_note(
        session_id=session_id,
        note_markdown=stored.note_markdown,
        summary=stored.summary,
        version=stored.version,
    )

    return {
        "session_id": session_id,
        "note_markdown": stored.note_markdown,
        "summary": stored.summary,
        "key_points": stored.key_points or [],
        "action_items": stored.action_items or [],
        "risk_flags": stored.risk_flags or [],
        "model": stored.model,
        "version": stored.version,
    }


def get_session_notes(session_id: int) -> dict[str, object]:
    with SessionLocal() as session:
        note = session.execute(
            select(SessionNote).where(SessionNote.session_id == session_id)
        ).scalar_one_or_none()
        if note is None:
            raise HTTPException(status_code=404, detail="Session notes not found")

    return {
        "session_id": session_id,
        "note_markdown": note.note_markdown,
        "summary": note.summary,
        "key_points": note.key_points or [],
        "action_items": note.action_items or [],
        "risk_flags": note.risk_flags or [],
        "model": note.model,
        "version": note.version,
    }


def enqueue_chunked_processing(session_id: int) -> dict[str, object]:
    with SessionLocal() as session:
        exists = session.get(Session, session_id)
        if exists is None:
            raise HTTPException(status_code=404, detail="Session not found")
        exists.status = "processing"
        exists.updated_at = datetime.utcnow()
        session.commit()

    result = celery_app.send_task(
        "server.tasks.session_processing.process_session_chunks",
        args=[session_id],
    )
    return {"session_id": session_id, "task_id": result.id, "status": "processing"}
