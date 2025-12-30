from __future__ import annotations

from pathlib import Path

from openai import OpenAI
from pydantic import BaseModel

from server.config import (
    get_openai_api_key,
    get_openai_max_retries,
    get_openai_proxy_url,
    get_openai_timeout_seconds,
    get_openai_transcription_model,
)

try:
    from pydantic import ConfigDict
except ImportError:  # pragma: no cover - fallback for pydantic<2
    ConfigDict = None


class TranscriptionAgent(BaseModel):
    client: OpenAI
    model: str

    if ConfigDict:
        model_config = ConfigDict(arbitrary_types_allowed=True)
    else:
        class Config:
            arbitrary_types_allowed = True

    @classmethod
    def from_env(cls) -> "TranscriptionAgent":
        api_key = get_openai_api_key()
        max_retries = get_openai_max_retries()
        proxy_url = get_openai_proxy_url()
        model = get_openai_transcription_model()
        timeout = get_openai_timeout_seconds()
        if not api_key or api_key == "YOUR_OPENAI_API_KEY":
            raise ValueError("Missing OpenAI API key")
        return cls(
            client=OpenAI(
                api_key=api_key,
                base_url=proxy_url,
                max_retries=max_retries,
                timeout=timeout,
            ),
            model=model,
        )

    def transcribe(self, file_path: Path) -> str:
        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        with file_path.open("rb") as audio_file:
            response = self.client.audio.transcriptions.create(
                model=self.model,
                file=audio_file,
            )

        return response.text
