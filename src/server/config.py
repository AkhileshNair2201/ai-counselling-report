from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_ROOT_DIR = Path(__file__).resolve().parents[2]
_ENV_PATH = _ROOT_DIR / ".env"
load_dotenv(_ENV_PATH)


def get_api_base_url() -> str:
    return os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1")


def get_database_url() -> str:
    user = os.getenv("POSTGRES_USER", "test")
    password = os.getenv("POSTGRES_PASSWORD", "1Kq84M(vO\\52")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5434")
    db_name = os.getenv("POSTGRES_DB", "ally")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"


def get_openai_api_key() -> str:
    return os.getenv("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY")


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def get_openai_proxy_url() -> str | None:
    proxy_url = os.getenv("OPENAI_PROXY_URL", "").strip()
    return proxy_url or None


def get_openai_timeout_seconds() -> float:
    return _get_float("OPENAI_TIMEOUT_SECONDS", 60.0)


def get_openai_max_retries() -> int:
    return _get_int("OPENAI_MAX_RETRIES", 2)


def get_openai_transcription_model() -> str:
    return os.getenv("OPENAI_TRANSCRIPTION_MODEL", "whisper-1")


def get_openai_embedding_model() -> str:
    return os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


def get_assemblyai_api_key() -> str:
    return os.getenv("ASSEMBLYAI_API_KEY", "")


def get_assemblyai_base_url() -> str:
    return os.getenv("ASSEMBLYAI_BASE_URL", "https://api.assemblyai.com")


def get_assemblyai_max_retries() -> int:
    return _get_int("ASSEMBLYAI_MAX_RETRIES", 2)


def get_assemblyai_retry_delay_seconds() -> float:
    return _get_float("ASSEMBLYAI_RETRY_DELAY_SECONDS", 2.0)


def get_qdrant_url() -> str:
    return os.getenv("QDRANT_URL", "http://localhost:6333")


def get_qdrant_api_key() -> str | None:
    api_key = os.getenv("QDRANT_API_KEY", "").strip()
    return api_key or None


def get_qdrant_collection() -> str:
    return os.getenv("QDRANT_COLLECTION", "transcripts")
