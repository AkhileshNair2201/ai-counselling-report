import logging

from fastapi import FastAPI
from sqlalchemy.exc import OperationalError
from fastapi.middleware.cors import CORSMiddleware

from server.api.api import router as api_router
from server.models.database import Base, engine

app = FastAPI(title="Audio Ingest API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api/v1", tags=["audio"])


@app.on_event("startup")
def on_startup() -> None:
    try:
        Base.metadata.create_all(bind=engine)
    except OperationalError:
        logging.getLogger(__name__).warning(
            "Database connection failed during startup. "
            "Start Postgres or check .env settings."
        )
