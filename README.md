# My Project

FastAPI service for ingesting audio files, plus a lightweight React UI in `src/web`.

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
uvicorn server.main:app --reload --app-dir src
```

## Processing (Sarvam STT + Diarization)

Set `SARVAM_API_KEY` in `.env`, then upload a session and enqueue chunked processing:

```bash
curl -F "file=@/path/to/audio.mp3" http://127.0.0.1:8000/api/v1/sessions/upload
curl -X POST http://127.0.0.1:8000/api/v1/sessions/<session_id>/process-large
```

## Vector Indexing (Qdrant)

The transcript is embedded after it is stored in Postgres and upserted into Qdrant.
Configure in `.env` as needed:

```bash
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=transcripts
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

## UI (React)

```bash
cd src/web
python3 -m http.server 5173
```

Open `http://127.0.0.1:5173`.

## Database Admin (pgAdmin)

pgAdmin runs at `http://127.0.0.1:5050`.

## Migrations

```bash
alembic upgrade head
```

## Background Processing (Celery)

Start Redis and the Celery worker for chunked processing:

```bash
docker-compose up -d redis
PYTHONPATH=src celery -A server.core.celery_app.celery_app worker -l info
```

Install ffmpeg (required for audio chunking):

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
```

Create a new migration:

```bash
alembic revision -m "describe_change"
```

Create and autogenerate (optional):

```bash
alembic revision --autogenerate -m "describe_change"
```

Rollback the last migration:

```bash
alembic downgrade -1
```
