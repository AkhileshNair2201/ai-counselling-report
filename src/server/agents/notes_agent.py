from __future__ import annotations

import json

from pydantic import BaseModel

from server.agents.llm_agent import LlmAgent

try:
    from pydantic import ConfigDict
except ImportError:  # pragma: no cover - fallback for pydantic<2
    ConfigDict = None


class NotesAgent(BaseModel):
    llm_agent: LlmAgent
    version: str = "v1"

    if ConfigDict:
        model_config = ConfigDict(arbitrary_types_allowed=True)
    else:
        class Config:
            arbitrary_types_allowed = True

    @classmethod
    def from_env(cls) -> "NotesAgent":
        return cls(llm_agent=LlmAgent.from_env())

    def _extract_json(self, content: str) -> dict[str, object] | None:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            return json.loads(content[start : end + 1])
        except json.JSONDecodeError:
            return None

    def generate_notes(self, *, transcript_text: str, diarized_segments: list[dict[str, object]] | None) -> dict[str, object]:
        transcript_text = transcript_text.strip()
        segment_hint = ""
        if diarized_segments:
            segment_hint = json.dumps(diarized_segments[:12], ensure_ascii=True)

        system_prompt = (
            "You are a clinical documentation assistant. Produce a structured counseling "
            "session note in JSON. Keep it concise, accurate, and professional."
        )
        user_prompt = (
            "Generate a counseling session note from the transcript below.\n\n"
            "Return JSON with keys: note_markdown, summary, key_points, action_items, risk_flags.\n"
            "Use markdown headings in note_markdown. key_points, action_items, risk_flags must be arrays of strings.\n\n"
            f"Transcript:\n{transcript_text}\n\n"
            f"Speaker segments (optional, sample):\n{segment_hint}\n"
        )
        response = self.llm_agent.llm.invoke(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
        content = (response.content or "").strip()
        payload = self._extract_json(content) or {}

        note_markdown = payload.get("note_markdown") or content or transcript_text
        summary = payload.get("summary")
        key_points = payload.get("key_points")
        action_items = payload.get("action_items")
        risk_flags = payload.get("risk_flags")

        model_name = getattr(self.llm_agent.llm, "model_name", None)
        if not model_name:
            model_name = getattr(self.llm_agent.llm, "model", "unknown")

        return {
            "note_markdown": str(note_markdown),
            "summary": str(summary) if isinstance(summary, str) else None,
            "key_points": key_points if isinstance(key_points, list) else None,
            "action_items": action_items if isinstance(action_items, list) else None,
            "risk_flags": risk_flags if isinstance(risk_flags, list) else None,
            "model": model_name,
            "version": self.version,
        }
