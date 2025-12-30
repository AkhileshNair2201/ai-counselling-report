from __future__ import annotations

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from server.config import get_openai_max_retries, get_openai_timeout_seconds
from server.settings import settings

try:
    from pydantic import ConfigDict
except ImportError:  # pragma: no cover - fallback for pydantic<2
    ConfigDict = None


class LlmAgent(BaseModel):
    llm: ChatOpenAI

    if ConfigDict:
        model_config = ConfigDict(arbitrary_types_allowed=True)
    else:
        class Config:
            arbitrary_types_allowed = True

    @classmethod
    def from_env(cls) -> "LlmAgent":
        if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "YOUR_OPENAI_API_KEY":
            raise ValueError("Missing OpenAI API key")

        max_retries = get_openai_max_retries()
        timeout = get_openai_timeout_seconds()
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_PROXY_URL,
            max_retries=max_retries,
            timeout=timeout,
        )
        return cls(llm=llm)
