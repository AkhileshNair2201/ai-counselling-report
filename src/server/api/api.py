from __future__ import annotations

import asyncio

from fastapi import APIRouter, File, UploadFile

from server.config import get_api_base_url
from server.services.services import (
    diarize_audio,
    diarize_session,
    generate_session_notes,
    get_session_detail,
    get_session_notes,
    get_transcript_segments,
    list_sessions,
    list_transcripts,
    save_audio,
    save_session_audio,
    transcribe_audio,
    transcribe_session,
)

router = APIRouter()


@router.post("/upload")
async def upload_audio(file: UploadFile = File(...)) -> dict[str, str]:
    return await save_audio(file)


@router.post("/sessions/upload")
async def upload_session_audio(file: UploadFile = File(...)) -> dict[str, object]:
    return await save_session_audio(file)


@router.post("/transcribe/{file_key}")
async def transcribe_uploaded_audio(file_key: str) -> dict[str, object]:
    return await asyncio.to_thread(transcribe_audio, file_key)


@router.post("/sessions/{session_id}/transcribe")
async def transcribe_session_audio(session_id: int) -> dict[str, object]:
    return await asyncio.to_thread(transcribe_session, session_id)


@router.post("/diarize/{file_key}")
async def diarize_uploaded_audio(file_key: str) -> dict[str, object]:
    return await asyncio.to_thread(diarize_audio, file_key)


@router.post("/sessions/{session_id}/diarize")
async def diarize_session_audio(session_id: int) -> dict[str, object]:
    return await asyncio.to_thread(diarize_session, session_id)


@router.post("/sessions/{session_id}/notes")
async def generate_notes(session_id: int) -> dict[str, object]:
    return await asyncio.to_thread(generate_session_notes, session_id)


@router.get("/transcripts")
async def list_transcribed_audio(
    page: int = 1, page_size: int = 10
) -> dict[str, object]:
    return await asyncio.to_thread(list_transcripts, page, page_size)


@router.get("/sessions")
async def list_counseling_sessions(
    page: int = 1, page_size: int = 10
) -> dict[str, object]:
    return await asyncio.to_thread(list_sessions, page, page_size)


@router.get("/transcripts/{file_key}")
async def get_transcript(file_key: str) -> dict[str, object]:
    return await asyncio.to_thread(get_transcript_segments, file_key)


@router.get("/sessions/{session_id}")
async def get_session(session_id: int) -> dict[str, object]:
    return await asyncio.to_thread(get_session_detail, session_id)


@router.get("/sessions/{session_id}/notes")
async def get_notes(session_id: int) -> dict[str, object]:
    return await asyncio.to_thread(get_session_notes, session_id)


@router.get("/config")
def get_config() -> dict[str, str]:
    return {"API_BASE_URL": get_api_base_url()}
