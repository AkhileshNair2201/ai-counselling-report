from __future__ import annotations

import asyncio

from fastapi import APIRouter, File, UploadFile

from server.config import get_api_base_url
from server.services.services import (
    diarize_audio,
    get_transcript_segments,
    list_transcripts,
    save_audio,
    transcribe_audio,
)

router = APIRouter()


@router.post("/upload")
async def upload_audio(file: UploadFile = File(...)) -> dict[str, str]:
    return await save_audio(file)


@router.post("/transcribe/{file_key}")
async def transcribe_uploaded_audio(file_key: str) -> dict[str, object]:
    return await asyncio.to_thread(transcribe_audio, file_key)


@router.post("/diarize/{file_key}")
async def diarize_uploaded_audio(file_key: str) -> dict[str, object]:
    return await asyncio.to_thread(diarize_audio, file_key)


@router.get("/transcripts")
async def list_transcribed_audio(
    page: int = 1, page_size: int = 10
) -> dict[str, object]:
    return await asyncio.to_thread(list_transcripts, page, page_size)


@router.get("/transcripts/{file_key}")
async def get_transcript(file_key: str) -> dict[str, object]:
    return await asyncio.to_thread(get_transcript_segments, file_key)


@router.get("/config")
def get_config() -> dict[str, str]:
    return {"API_BASE_URL": get_api_base_url()}
