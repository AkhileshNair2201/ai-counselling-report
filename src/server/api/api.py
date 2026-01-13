from __future__ import annotations

import asyncio

from fastapi import APIRouter, File, UploadFile

from server.config import get_api_base_url
from server.services.services import (
    enqueue_chunked_processing,
    get_session_detail,
    get_session_notes,
    get_transcript_segments,
    list_sessions,
    list_transcripts,
    save_audio,
    save_session_audio,
)

router = APIRouter()


@router.post("/upload")
async def upload_audio(file: UploadFile = File(...)) -> dict[str, str]:
    return await save_audio(file)


@router.post("/sessions/upload")
async def upload_session_audio(file: UploadFile = File(...)) -> dict[str, object]:
    return await save_session_audio(file)


@router.post("/sessions/{session_id}/process-large")
async def process_large_audio(session_id: int) -> dict[str, object]:
    return await asyncio.to_thread(enqueue_chunked_processing, session_id)


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
