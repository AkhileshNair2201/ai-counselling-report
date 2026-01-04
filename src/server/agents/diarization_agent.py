from __future__ import annotations

from pathlib import Path
import time

import assemblyai as aai
from pydantic import BaseModel

from server.config import (
    get_assemblyai_api_key,
    get_assemblyai_base_url,
    get_assemblyai_max_retries,
    get_assemblyai_retry_delay_seconds,
)

try:
    from pydantic import ConfigDict
except ImportError:  # pragma: no cover - fallback for pydantic<2
    ConfigDict = None


class DiarizationAgent(BaseModel):
    api_key: str
    base_url: str
    max_retries: int
    retry_delay_seconds: float

    if ConfigDict:
        model_config = ConfigDict(frozen=True)
    else:
        class Config:
            allow_mutation = False

    @classmethod
    def from_env(cls) -> "DiarizationAgent":
        api_key = get_assemblyai_api_key()
        base_url = get_assemblyai_base_url().rstrip("/")
        if base_url.endswith("/v2"):
            base_url = base_url[: -len("/v2")]
        max_retries = get_assemblyai_max_retries()
        retry_delay_seconds = get_assemblyai_retry_delay_seconds()
        if not api_key:
            raise ValueError("Missing AssemblyAI API key")
        return cls(
            api_key=api_key,
            base_url=base_url,
            max_retries=max_retries,
            retry_delay_seconds=retry_delay_seconds,
        )

    def diarize(self, file_path: Path, content_type: str | None) -> dict[str, object]:
        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        aai.settings.api_key = self.api_key
        if hasattr(aai.settings, "base_url"):
            aai.settings.base_url = self.base_url

        config = aai.TranscriptionConfig(
            speech_models=["universal"],
            speaker_labels=True,
            punctuate=True,
            format_text=True,
        )

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                transcript = aai.Transcriber(config=config).transcribe(
                    str(file_path)
                )
                if transcript.status == "error":
                    raise RuntimeError(
                        f"Transcription failed: {transcript.error}"
                    )

                utterances = transcript.utterances or []
                segments = []
                for utterance in utterances:
                    start_ms = getattr(utterance, "start", None)
                    end_ms = getattr(utterance, "end", None)
                    start = (
                        start_ms / 1000.0
                        if isinstance(start_ms, (int, float))
                        else None
                    )
                    end = (
                        end_ms / 1000.0 if isinstance(end_ms, (int, float)) else None
                    )
                    speaker = getattr(utterance, "speaker", None)
                    text = getattr(utterance, "text", "") or ""
                    segments.append(
                        {
                            "speaker": f"SPEAKER_{speaker}"
                            if speaker is not None
                            else "SPEAKER_UNKNOWN",
                            "timestamp": {"start": start, "end": end},
                            "text": text,
                        }
                    )

                text = (transcript.text or "").strip()
                return {"text": text, "segments": segments}
            except Exception as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(self.retry_delay_seconds)

        raise RuntimeError(str(last_error) if last_error else "Diarization failed")
