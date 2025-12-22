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
