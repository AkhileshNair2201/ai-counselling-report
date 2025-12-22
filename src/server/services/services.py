from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from server.models.audio import AudioFile
from server.models.database import SessionLocal

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
