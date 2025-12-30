from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy import select

from server.models.audio import AudioFile
from server.models.database import SessionLocal
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


def transcribe_audio(file_key: str) -> dict[str, str]:
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

    transcript = agent.transcribe(audio_path)

    return {"file_key": file_key, "transcript": transcript}
