# Plan (Counseling Session Notes Product)

## Product Intent
Turn counseling session audio recordings into clear, accurate, and well-structured session notes with optional speaker labeling and searchable indexing.

## Current Architecture
- FastAPI backend for session upload, transcription, diarization, and note generation.
- Postgres via SQLAlchemy/Alembic for sessions, transcripts, and notes.
- Qdrant for embeddings of structured notes.
- React UI for session creation and session list + notes viewing.

## Database Schema
### `sessions`
- `id` (int, PK)
- `title` (string)
- `status` (string: uploaded/transcribed/noted)
- `session_date` (datetime, nullable)
- `created_at` (datetime)
- `updated_at` (datetime)

### `audio_files`
- `id` (int, PK)
- `session_id` (int, FK -> sessions.id, indexed)
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

### `session_notes`
- `id` (int, PK)
- `session_id` (int, FK -> sessions.id, unique, indexed)
- `note_markdown` (text)
- `summary` (text, nullable)
- `key_points` (json, nullable)
- `action_items` (json, nullable)
- `risk_flags` (json, nullable)
- `model` (string)
- `version` (string)
- `created_at` (datetime)
- `updated_at` (datetime)

## API Flow
1) `POST /sessions/upload` -> create session + audio.
2) `POST /sessions/{session_id}/transcribe` -> generate transcript + segments.
3) `POST /sessions/{session_id}/diarize` -> add speaker labels (optional).
4) `POST /sessions/{session_id}/notes` -> generate structured counseling notes.
5) `GET /sessions` -> list sessions + notes status.
6) `GET /sessions/{session_id}` -> session detail.
7) `GET /sessions/{session_id}/notes` -> structured notes payload.

## LLM / Agent Design
- `NotesAgent` consumes transcript + diarization segments and outputs structured JSON notes.
- Final note is stored in `session_notes` and indexed for retrieval.
- Transcription/diarization agents remain upstream steps.

## Vector Store
- Indexes `session_notes.note_markdown` plus summary metadata.
- Payload includes `session_id`, `version`, and a type marker.

## UI Changes
- "New Session" and "Sessions" navigation.
- Upload view framed as counseling session note generation.
- Session list shows notes availability and opens note detail in a modal.

## Config / Runtime Dependencies (Unchanged)
- Postgres via `.env`
- Qdrant via `QDRANT_URL`, `QDRANT_COLLECTION`, optional `QDRANT_API_KEY`
- OpenAI via `OPENAI_API_KEY`, `OPENAI_TRANSCRIPTION_MODEL`, `OPENAI_EMBEDDING_MODEL`
- AssemblyAI via `ASSEMBLYAI_API_KEY`, `ASSEMBLYAI_BASE_URL`
