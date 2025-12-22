from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from server.config import get_api_base_url
from server.services.services import save_audio

router = APIRouter()


@router.post("/upload")
async def upload_audio(file: UploadFile = File(...)) -> dict[str, str]:
    return await save_audio(file)


@router.get("/config")
def get_config() -> dict[str, str]:
    return {"API_BASE_URL": get_api_base_url()}
