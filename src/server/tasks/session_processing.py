from __future__ import annotations

import asyncio
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

from httpx import TimeoutException
from openai import APITimeoutError
from sqlalchemy import delete, select

from server.config import get_audio_chunk_seconds
from server.core.celery_app import celery_app
from server.models.audio import AudioFile
from server.models.audio_chunk import AudioChunk
from server.models.chunk_transcript import ChunkTranscript
from server.models.session import Session
from server.models.session_note import SessionNote
from server.models.transcript import Transcript
from server.models.database import SessionLocal
from server.agents.notes_agent import NotesAgent
from server.agents.sarvam_stt_agent import SarvamSttAgent
from server.services.services import _calculate_duration_seconds, _resolve_audio_path
from server.services.vector_store import upsert_session_note_vector


def _chunk_audio(
    *,
    audio_path: Path,
    chunk_seconds: int,
    output_dir: Path,
) -> list[Path]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for chunked processing")

    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = audio_path.suffix or ".wav"
    pattern = output_dir / f"chunk_%05d{suffix}"

    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(audio_path),
        "-f",
        "segment",
        "-segment_time",
        str(chunk_seconds),
        "-reset_timestamps",
        "1",
        "-c",
        "copy",
        str(pattern),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffmpeg chunking failed")

    return sorted(output_dir.glob(f"chunk_*{suffix}"))


def _offset_segments(
    segments: list[dict[str, object]] | None, offset_seconds: float
) -> list[dict[str, object]] | None:
    if not segments:
        return segments
    updated = []
    for segment in segments:
        if not isinstance(segment, dict):
            updated.append(segment)
            continue
        timestamp = segment.get("timestamp")
        if isinstance(timestamp, dict):
            start = timestamp.get("start")
            end = timestamp.get("end")
            if isinstance(start, (int, float)):
                timestamp["start"] = float(start) + offset_seconds
            if isinstance(end, (int, float)):
                timestamp["end"] = float(end) + offset_seconds
        updated.append(segment)
    return updated


def _merge_text(texts: list[str]) -> str:
    return "\n".join([text.strip() for text in texts if text and text.strip()]).strip()


def _generate_notes_with_retry(
    *,
    notes_agent: NotesAgent,
    transcript_text: str,
    diarized_segments: list[dict[str, object]] | None,
    max_retries: int = 3,
    retry_delay_seconds: float = 2.0,
) -> dict[str, object]:
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return notes_agent.generate_notes(
                transcript_text=transcript_text,
                diarized_segments=diarized_segments,
            )
        except Exception as exc:
            last_error = exc
            if attempt >= max_retries:
                break
            time.sleep(retry_delay_seconds)
    raise RuntimeError(str(last_error) if last_error else "Notes generation failed")


def _process_chunk(
    *,
    audio_id: int,
    chunk_file: Path,
    chunk_index: int,
    start_seconds: float,
    end_seconds: float,
) -> int:
    with SessionLocal() as session:
        chunk = AudioChunk(
            audio_file_id=audio_id,
            chunk_index=chunk_index,
            file_path=str(chunk_file),
            start_seconds=start_seconds,
            end_seconds=end_seconds,
        )
        session.add(chunk)
        session.commit()
        session.refresh(chunk)

    sarvam_agent = SarvamSttAgent.from_env()
    transcript_payload = sarvam_agent.transcribe_with_diarization(chunk_file)

    transcript_text = str(transcript_payload.get("text", ""))
    diarized_segments = transcript_payload.get("segments", [])
    diarized_text = transcript_text
    segments: list[dict[str, object]] = []

    duration_seconds = (
        _calculate_duration_seconds(diarized_segments)
        if isinstance(diarized_segments, list)
        else None
    )

    with SessionLocal() as session:
        existing = session.execute(
            select(ChunkTranscript).where(ChunkTranscript.audio_chunk_id == chunk.id)
        ).scalar_one_or_none()
        if existing is None:
            record = ChunkTranscript(
                audio_chunk_id=chunk.id,
                text=transcript_text,
                segments=segments,
                diarized_text=diarized_text,
                diarized_segments=diarized_segments,
                duration_seconds=duration_seconds,
            )
            session.add(record)
        else:
            existing.text = transcript_text
            existing.segments = segments
            existing.diarized_text = diarized_text
            existing.diarized_segments = diarized_segments
            existing.duration_seconds = duration_seconds
        session.commit()

    return chunk.id


async def _process_chunks_concurrently(
    *,
    chunk_inputs: list[tuple[int, Path, float, float]],
    audio_id: int,
) -> list[int]:
    if not chunk_inputs:
        return []

    max_parallel = min(4, len(chunk_inputs))
    semaphore = asyncio.Semaphore(max_parallel)

    async def run_one(
        chunk_index: int, chunk_file: Path, start_seconds: float, end_seconds: float
    ) -> int:
        async with semaphore:
            return await asyncio.to_thread(
                _process_chunk,
                audio_id=audio_id,
                chunk_file=chunk_file,
                chunk_index=chunk_index,
                start_seconds=start_seconds,
                end_seconds=end_seconds,
            )

    tasks = [
        asyncio.create_task(run_one(index, chunk_file, start, end))
        for index, chunk_file, start, end in chunk_inputs
    ]
    return await asyncio.gather(*tasks)


@celery_app.task(
    name="server.tasks.session_processing.process_session_chunks",
    autoretry_for=(APITimeoutError, TimeoutException),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def process_session_chunks(session_id: int) -> dict[str, object]:
    with SessionLocal() as session:
        row = session.execute(
            select(Session, AudioFile)
            .join(AudioFile, AudioFile.session_id == Session.id)
            .where(Session.id == session_id)
        ).first()
        if row is None:
            raise RuntimeError("Session not found")
        session_row, audio = row
        audio_id = audio.id
        audio_file_key = audio.file_key
        session_row.status = "processing"
        session_row.updated_at = datetime.utcnow()
        session.commit()

    audio_path = _resolve_audio_path(audio_file_key)
    chunk_seconds = min(get_audio_chunk_seconds(), 25)
    chunks_dir = audio_path.parent / "chunks" / audio_file_key
    chunk_files = _chunk_audio(
        audio_path=audio_path,
        chunk_seconds=chunk_seconds,
        output_dir=chunks_dir,
    )
    if not chunk_files:
        raise RuntimeError("No chunks created for audio file")

    with SessionLocal() as session:
        chunk_ids = session.execute(
            select(AudioChunk.id).where(AudioChunk.audio_file_id == audio_id)
        ).scalars().all()
        if chunk_ids:
            session.execute(
                delete(ChunkTranscript).where(
                    ChunkTranscript.audio_chunk_id.in_(chunk_ids)
                )
            )
        session.execute(
            delete(AudioChunk).where(AudioChunk.audio_file_id == audio_id)
        )
        session.commit()

    chunk_inputs: list[tuple[int, Path, float, float]] = []
    for index, chunk_file in enumerate(chunk_files):
        start_seconds = float(index * chunk_seconds)
        end_seconds = start_seconds + chunk_seconds
        chunk_inputs.append((index, chunk_file, start_seconds, end_seconds))

    asyncio.run(
        _process_chunks_concurrently(
            chunk_inputs=chunk_inputs,
            audio_id=audio_id,
        )
    )

    with SessionLocal() as session:
        rows = session.execute(
            select(AudioChunk, ChunkTranscript)
            .join(ChunkTranscript, ChunkTranscript.audio_chunk_id == AudioChunk.id)
            .where(AudioChunk.audio_file_id == audio_id)
            .order_by(AudioChunk.chunk_index.asc())
        ).all()

    merged_texts: list[str] = []
    merged_segments: list[dict[str, object]] = []
    merged_diarized_texts: list[str] = []
    merged_diarized_segments: list[dict[str, object]] = []

    for chunk, transcript in rows:
        offset = float(chunk.start_seconds or 0)
        if transcript.text:
            merged_texts.append(transcript.text)
        if transcript.segments:
            merged_segments.extend(_offset_segments(transcript.segments, offset) or [])
        if transcript.diarized_text:
            merged_diarized_texts.append(transcript.diarized_text)
        if transcript.diarized_segments:
            merged_diarized_segments.extend(
                _offset_segments(transcript.diarized_segments, offset) or []
            )

    merged_text = _merge_text(merged_texts)
    merged_diarized_text = _merge_text(merged_diarized_texts) or merged_text
    merged_duration = _calculate_duration_seconds(
        merged_diarized_segments or merged_segments
    )

    with SessionLocal() as session:
        existing = session.execute(
            select(Transcript).where(Transcript.audio_file_id == audio_id)
        ).scalar_one_or_none()
        if existing is None:
            record = Transcript(
                audio_file_id=audio_id,
                text=merged_text,
                segments=merged_segments,
                diarized_text=merged_diarized_text,
                diarized_segments=merged_diarized_segments,
                duration_seconds=merged_duration,
            )
            session.add(record)
        else:
            existing.text = merged_text
            existing.segments = merged_segments
            existing.diarized_text = merged_diarized_text
            existing.diarized_segments = merged_diarized_segments
            existing.duration_seconds = merged_duration
        session.commit()

    notes_agent = NotesAgent.from_env()
    try:
        notes_payload = _generate_notes_with_retry(
            notes_agent=notes_agent,
            transcript_text=merged_diarized_text or merged_text,
            diarized_segments=merged_diarized_segments or merged_segments,
        )
    except Exception as exc:
        with SessionLocal() as session:
            session_row = session.get(Session, session_id)
            if session_row:
                session_row.status = "transcribed"
                session_row.updated_at = datetime.utcnow()
            session.commit()
        return {
            "session_id": session_id,
            "chunks": len(chunk_files),
            "status": "transcribed",
            "notes_status": "failed",
            "error": str(exc),
        }

    with SessionLocal() as session:
        existing_note = session.execute(
            select(SessionNote).where(SessionNote.session_id == session_id)
        ).scalar_one_or_none()
        if existing_note is None:
            record = SessionNote(
                session_id=session_id,
                note_markdown=notes_payload["note_markdown"],
                summary=notes_payload["summary"],
                key_points=notes_payload["key_points"],
                action_items=notes_payload["action_items"],
                risk_flags=notes_payload["risk_flags"],
                model=notes_payload["model"],
                version=notes_payload["version"],
            )
            session.add(record)
        else:
            existing_note.note_markdown = notes_payload["note_markdown"]
            existing_note.summary = notes_payload["summary"]
            existing_note.key_points = notes_payload["key_points"]
            existing_note.action_items = notes_payload["action_items"]
            existing_note.risk_flags = notes_payload["risk_flags"]
            existing_note.model = notes_payload["model"]
            existing_note.version = notes_payload["version"]
            existing_note.updated_at = datetime.utcnow()
        session_row = session.get(Session, session_id)
        if session_row:
            session_row.status = "noted"
            session_row.updated_at = datetime.utcnow()
        session.commit()

    upsert_session_note_vector(
        session_id=session_id,
        note_markdown=notes_payload["note_markdown"],
        summary=notes_payload["summary"],
        version=notes_payload["version"],
    )

    return {
        "session_id": session_id,
        "chunks": len(chunk_files),
        "status": "noted",
        "notes_status": "ready",
    }
