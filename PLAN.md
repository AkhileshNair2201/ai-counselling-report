# Plan (Current State)

## Scope
FastAPI backend for audio ingestion, transcription, diarization, and vector indexing, plus a lightweight React UI for uploads and transcript browsing.

## Database Schema (Postgres)
Data is managed with SQLAlchemy models and Alembic migrations.

### `audio_files`
- `id` (int, PK)
- `file_key` (string, unique, indexed)
- `original_filename` (string)
- `content_type` (string)
- `created_at` (datetime)

### `transcripts`
- `id` (int, PK)
- `audio_file_id` (int, FK -> audio_files.id, unique, indexed)
- `text` (text)
- `segments` (json, nullable)
- `diarized_text` (text, nullable)
- `diarized_segments` (json, nullable)
- `duration_seconds` (float, nullable)
- `created_at` (datetime)
- `updated_at` (datetime)

## Core Data Flow
1) Upload audio -> validate content type -> write to `src/server/uploads/` -> create `audio_files` row.
2) Transcribe -> fetch audio by `file_key` -> OpenAI Whisper transcription -> write/update `transcripts` row.
3) Diarize -> fetch audio by `file_key` -> AssemblyAI diarization -> write/update diarization fields.
4) Indexing -> embed transcript text with OpenAI embeddings -> upsert into Qdrant with metadata payload.
5) UI -> calls API to upload, transcribe, diarize, list transcripts, and view transcript segments.

## APIs (FastAPI)
Base prefix: `/api/v1`

- `POST /upload`  
  Uploads an audio file; returns `{file_key, filename, path, content_type}`.
- `POST /transcribe/{file_key}`  
  Runs OpenAI transcription; returns `{file_key, text, segments}`.
- `POST /diarize/{file_key}`  
  Runs AssemblyAI diarization; returns `{file_key, text, segments}`.
- `GET /transcripts?page=&page_size=`  
  Paginated transcript list with durations and diarization availability.
- `GET /transcripts/{file_key}`  
  Returns transcript text + segments for a file.
- `GET /config`  
  Returns `{API_BASE_URL}` for the UI.

## LLM / Agent Design
All agents are thin, environment-configured wrappers that isolate external API calls.

### TranscriptionAgent
- Provider: OpenAI `audio.transcriptions.create`
- Model: `OPENAI_TRANSCRIPTION_MODEL` (default `whisper-1`)
- Output: `text` + `segments` (timestamped)
- Used in: `transcribe_audio` service

### DiarizationAgent
- Provider: AssemblyAI
- Features: speaker labels, punctuation, formatted text
- Output: `text` + `segments` with speaker labels and timestamps
- Used in: `diarize_audio` service

### LlmAgent
- Provider: OpenAI (LangChain `ChatOpenAI`)
- Model: `gpt-4o-mini`
- Current use: initialized but not yet integrated into service flows

## Vector Store (Qdrant)
- Embeddings: OpenAI embeddings via LangChain (`OpenAIEmbeddings`)
- Collection: `QDRANT_COLLECTION` (default `transcripts`)
- Payload fields: `file_key`, `text`, `segment_count`, `diarized`
- Trigger: after transcript or diarization stored in Postgres

## UI (React)
- Single-page frontend in `src/web` using fetch calls to FastAPI.
- Supports upload, transcription, diarization, transcript list view, and segment modal.
- Reads `/api/v1/config` to discover API base URL.

## Config / Runtime Dependencies
- Postgres: via `.env` (see `docker-compose.yml` for defaults)
- Qdrant: `QDRANT_URL`, `QDRANT_COLLECTION`, optional `QDRANT_API_KEY`
- OpenAI: `OPENAI_API_KEY`, `OPENAI_TRANSCRIPTION_MODEL`, `OPENAI_EMBEDDING_MODEL`
- AssemblyAI: `ASSEMBLYAI_API_KEY`, `ASSEMBLYAI_BASE_URL`
