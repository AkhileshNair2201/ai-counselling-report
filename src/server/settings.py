from __future__ import annotations

from pydantic import BaseModel

from server.config import get_openai_api_key, get_openai_proxy_url

try:
    from pydantic import ConfigDict
except ImportError:  # pragma: no cover - fallback for pydantic<2
    ConfigDict = None


class Settings(BaseModel):
    OPENAI_API_KEY: str
    OPENAI_PROXY_URL: str | None

    if ConfigDict:
        model_config = ConfigDict(frozen=True)
    else:
        class Config:
            allow_mutation = False


settings = Settings(
    OPENAI_API_KEY=get_openai_api_key(),
    OPENAI_PROXY_URL=get_openai_proxy_url(),
)
