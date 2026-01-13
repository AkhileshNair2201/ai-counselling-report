# Plan (Counseling Session Notes Product)

## Product Intent
Turn counseling session audio recordings into clear, accurate, and well-structured session notes with speaker labeling and searchable indexing.

## Current Architecture
- FastAPI backend for session upload, transcription + translation, diarization, and note generation.
- Postgres via SQLAlchemy/Alembic for sessions, transcripts, and notes.
- Qdrant for embeddings of structured notes.
- React UI for session creation and session list + notes viewing.

## Updated Requirement: English Transcripts + Diarization (SarvamAI)
- All transcriptions should return English text, even for multilingual audio.
- Use SarvamAI speech-to-text translation with inbuilt diarization to normalize output to English.
- Use `SARVAM_TRANSLATION_MODEL` (default `saaras:v2.5`).
- SarvamAI REST translate is intended for sub-30s audio; chunked processing should cap chunk length accordingly.

## New Requirement: Chunked Processing (Planned)
Large audio files should be chunked and processed asynchronously. The new flow uses:
- **FFmpeg** to split audio into ordered chunks.
- **Celery** to process chunks in the background.
- **Aggregation** to coalesce chunk transcripts/notes into a final session record.

### Optimization (Planned)
- Use **asyncio** inside the Celery task to process multiple chunks in parallel.
- Keep task-level isolation in Celery, but run concurrent API calls per chunk to improve throughput.

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
### Planned (Chunked + Background)
1) `POST /sessions/upload` -> create session + audio.
2) Enqueue Celery task: **chunk audio** with FFmpeg and store ordered chunks.
3) Enqueue per-chunk Celery tasks:
   - transcribe + translate + diarize chunk (SarvamAI, English output)
4) Enqueue aggregation task:
   - coalesce transcripts and diarization segments in order
   - generate session notes from the merged transcript
5) Store merged transcript + notes back into `transcripts` and `session_notes`.
6) Index final notes into Qdrant.

## LLM / Agent Design
- `NotesAgent` consumes an English transcript + diarization segments and outputs structured JSON notes.
- Final note is stored in `session_notes` and indexed for retrieval.
- A single Sarvam STT+diarization agent handles speech-to-text translation and speaker labeling.

### Planned Changes emphasized by chunking
- Notes generation uses the **merged** transcript + diarized segments.
- Chunk metadata must preserve ordering for deterministic coalescing.

## Vector Store
- Indexes `session_notes.note_markdown` plus summary metadata.
- Payload includes `session_id`, `version`, and a type marker.

## UI Changes
- Remove separate "Transcribe" / "Diarize" / "Generate Notes" actions.
- Keep only **"Process Large Audio"** to trigger the chunked Celery workflow.
- Session list allows viewing **Transcript** (diarized segments) and **Notes**.

## Config / Runtime Dependencies (Unchanged)
- Postgres via `.env`
- Qdrant via `QDRANT_URL`, `QDRANT_COLLECTION`, optional `QDRANT_API_KEY`
- OpenAI via `OPENAI_API_KEY`, `OPENAI_EMBEDDING_MODEL`
- SarvamAI via `SARVAM_API_KEY`, optional `SARVAM_TRANSLATION_MODEL` (defaults to `saaras:v2.5`)
