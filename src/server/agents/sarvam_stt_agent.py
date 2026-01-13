from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path

from pydantic import BaseModel
from sarvamai import AsyncSarvamAI

from server.config import (
    get_sarvam_api_key,
    get_sarvam_num_speakers,
    get_sarvam_prompt,
    get_sarvam_translation_model,
)

try:
    from pydantic import ConfigDict
except ImportError:  # pragma: no cover - fallback for pydantic<2
    ConfigDict = None


class SarvamSttAgent(BaseModel):
    client: AsyncSarvamAI
    model: str
    num_speakers: int | None
    prompt: str | None

    if ConfigDict:
        model_config = ConfigDict(arbitrary_types_allowed=True)
    else:
        class Config:
            arbitrary_types_allowed = True

    @classmethod
    def from_env(cls) -> "SarvamSttAgent":
        api_key = get_sarvam_api_key()
        model = get_sarvam_translation_model()
        if not api_key:
            raise ValueError("Missing SarvamAI API key")
        return cls(
            client=AsyncSarvamAI(api_subscription_key=api_key),
            model=model,
            num_speakers=get_sarvam_num_speakers(),
            prompt=get_sarvam_prompt(),
        )

    def transcribe_with_diarization(self, file_path: Path) -> dict[str, object]:
        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")
        return asyncio.run(self._transcribe_async(file_path))

    async def _transcribe_async(self, file_path: Path) -> dict[str, object]:
        job = await self.client.speech_to_text_translate_job.create_job(
            model=self.model,
            with_diarization=True,
            num_speakers=self.num_speakers,
            prompt=self.prompt,
        )
        await job.upload_files(file_paths=[str(file_path)])
        await job.start()
        await job.wait_until_complete()

        results = await job.get_file_results()
        successful = (
            results.get("successful", [])
            if isinstance(results, dict)
            else []
        )
        failed = (
            results.get("failed", [])
            if isinstance(results, dict)
            else []
        )
        if not successful:
            failure_message = "Sarvam STT job failed"
            if failed:
                failure_message = (
                    failed[0].get("error_message") or failure_message
                )
            raise RuntimeError(failure_message)

        output_dir = Path(
            tempfile.mkdtemp(prefix="sarvam_outputs_", dir=file_path.parent)
        )
        try:
            await job.download_outputs(output_dir=str(output_dir))
            output_file = self._find_output_file(
                output_dir, successful[0].get("file_name", file_path.name)
            )
            return self._parse_output(output_file)
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)

    def _find_output_file(self, output_dir: Path, file_name: str) -> Path:
        stem = Path(file_name).stem
        candidates = sorted(output_dir.glob(f"{stem}*"))
        if not candidates:
            candidates = sorted(output_dir.iterdir())
        if not candidates:
            raise RuntimeError("Sarvam output files not found")
        return candidates[0]

    def _parse_output(self, output_file: Path) -> dict[str, object]:
        suffix = output_file.suffix.lower()
        if suffix == ".json":
            data = json.loads(output_file.read_text(encoding="utf-8"))
            text = self._extract_text(data)
            segments = self._extract_segments(data)
        else:
            text = output_file.read_text(encoding="utf-8", errors="ignore")
            segments = []

        if not text and segments:
            text = " ".join(segment.get("text", "") for segment in segments).strip()

        return {"text": text or "", "segments": segments}

    def _extract_text(self, data: object) -> str:
        if isinstance(data, dict):
            for key in ("transcript", "text", "full_text", "translation", "output"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            nested = data.get("result")
            if isinstance(nested, dict):
                return self._extract_text(nested)
        return ""

    def _extract_segments(self, data: object) -> list[dict[str, object]]:
        if isinstance(data, dict):
            diarized = data.get("diarized_transcript")
            if isinstance(diarized, dict):
                entries = diarized.get("entries")
                if isinstance(entries, list):
                    return self._normalize_diarized_entries(entries)
            for key in ("segments", "utterances", "diarized_segments", "speaker_segments"):
                value = data.get(key)
                if isinstance(value, list):
                    return self._normalize_segments(value)
            diarization = data.get("diarization")
            if isinstance(diarization, dict):
                for key in ("segments", "utterances"):
                    value = diarization.get(key)
                    if isinstance(value, list):
                        return self._normalize_segments(value)
        return []

    def _normalize_segments(
        self, raw_segments: list[object]
    ) -> list[dict[str, object]]:
        segments: list[dict[str, object]] = []
        for raw in raw_segments:
            if not isinstance(raw, dict):
                continue
            text = (
                raw.get("text")
                or raw.get("utterance")
                or raw.get("transcript")
                or ""
            )
            start = self._extract_time(raw, "start")
            end = self._extract_time(raw, "end")
            speaker = (
                raw.get("speaker")
                or raw.get("speaker_label")
                or raw.get("speaker_id")
                or raw.get("speaker_name")
            )
            segments.append(
                {
                    "speaker": self._normalize_speaker(speaker),
                    "timestamp": {"start": start, "end": end},
                    "text": text,
                }
            )
        return segments

    def _normalize_diarized_entries(
        self, entries: list[object]
    ) -> list[dict[str, object]]:
        segments: list[dict[str, object]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            text = entry.get("transcript") or entry.get("text") or ""
            start = entry.get("start_time_seconds")
            end = entry.get("end_time_seconds")
            start_value = float(start) if isinstance(start, (int, float)) else None
            end_value = float(end) if isinstance(end, (int, float)) else None
            speaker = entry.get("speaker_id")
            segments.append(
                {
                    "speaker": self._normalize_speaker(speaker),
                    "timestamp": {"start": start_value, "end": end_value},
                    "text": text,
                }
            )
        return segments

    def _extract_time(self, raw: dict[str, object], prefix: str) -> float | None:
        for key in (
            f"{prefix}_ms",
            f"{prefix}_time_ms",
            f"{prefix}_time",
            f"{prefix}Time",
            prefix,
        ):
            value = raw.get(key)
            if isinstance(value, (int, float)):
                return (
                    float(value) / 1000.0
                    if "ms" in key.lower()
                    else float(value)
                )
        return None

    def _normalize_speaker(self, speaker: object) -> str:
        if speaker is None:
            return "SPEAKER_UNKNOWN"
        if isinstance(speaker, (int, float)):
            return f"SPEAKER_{int(speaker)}"
        if isinstance(speaker, str):
            if speaker.startswith("SPEAKER_"):
                return speaker
            return f"SPEAKER_{speaker}"
        return "SPEAKER_UNKNOWN"
