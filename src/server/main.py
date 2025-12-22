from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.api.api import router as api_router

app = FastAPI(title="Audio Ingest API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api/v1", tags=["audio"])
