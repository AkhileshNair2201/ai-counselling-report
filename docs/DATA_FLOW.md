# Data Flow & Key Functions

This document explains how counseling session audio moves through the system and highlights the core functions that implement each step.

## High-Level Flow (UI -> API -> DB)
1) Upload a session recording.
2) Transcribe/diarize immediately or queue chunked background processing.
3) Generate structured session notes.
4) Store transcripts + notes in Postgres and index notes in Qdrant.
5) UI lists sessions and shows generated notes.

## API Surface (FastAPI)
All routes are under `/api/v1` (see `src/server/api/api.py`).

- `POST /sessions/upload` -> `save_session_audio`
- `POST /sessions/{session_id}/transcribe` -> `transcribe_session`
- `POST /sessions/{session_id}/diarize` -> `diarize_session`
- `POST /sessions/{session_id}/notes` -> `generate_session_notes`
- `POST /sessions/{session_id}/process-large` -> `enqueue_chunked_processing`
- `GET /sessions` -> `list_sessions`
- `GET /sessions/{session_id}` -> `get_session_detail`
- `GET /sessions/{session_id}/notes` -> `get_session_notes`

## Core Services (Synchronous)
Defined in `src/server/services/services.py`.

### Upload
- `save_session_audio(file)`
  - Validates audio type
  - Writes the file to `src/server/uploads/`
  - Creates `sessions` + `audio_files` rows

### Transcription
- `transcribe_session(session_id)`
  - Fetches session + audio by `session_id`
  - Uses `TranscriptionAgent` (OpenAI Whisper)
  - Saves/updates `transcripts`
  - Updates `sessions.status` -> `transcribed`

### Diarization
- `diarize_session(session_id)`
  - Uses `DiarizationAgent` (AssemblyAI)
  - Stores diarized text/segments into `transcripts`
  - Updates `sessions.status` -> `transcribed`

### Note Generation
- `generate_session_notes(session_id)`
  - Uses `NotesAgent` (LLM) to create structured note JSON
  - Writes to `session_notes`
  - Updates `sessions.status` -> `noted`
  - Indexes notes into Qdrant via `upsert_session_note_vector`

### Chunked Processing Entry Point
- `enqueue_chunked_processing(session_id)`
  - Marks session as `processing`
  - Sends a Celery task for chunking + aggregation

## Background Processing (Chunked)
Implemented in `src/server/tasks/session_processing.py`.

### Task: `process_session_chunks(session_id)`
1) Load session + audio metadata.
2) Split audio into ordered chunks with FFmpeg (`_chunk_audio`).
3) For each chunk:
   - Transcribe via `TranscriptionAgent`
   - Diarize via `DiarizationAgent`
   - Store chunk metadata in `audio_chunks`
   - Store chunk transcript in `chunk_transcripts`
4) Merge all chunk transcripts in order:
   - `_merge_text` concatenates text
   - `_offset_segments` shifts timestamps by chunk offset
5) Save merged transcript in `transcripts`
6) Generate final notes using `NotesAgent`
7) Save notes in `session_notes` and index in Qdrant

Retry behavior:
- Celery retries on OpenAI/HTTP timeouts with backoff and jitter.

## Agents (LLM & Speech)
Located in `src/server/agents/`.

- `TranscriptionAgent` (OpenAI Whisper)
- `DiarizationAgent` (AssemblyAI)
- `NotesAgent` (LLM) in `src/server/agents/notes_agent.py`
  - Produces JSON: `note_markdown`, `summary`, `key_points`, `action_items`, `risk_flags`

## Vector Indexing
In `src/server/services/vector_store.py`.

- `upsert_session_note_vector(...)`
  - Embeds `note_markdown`
  - Stores payload with `session_id`, `version`, and `summary`

## Database Tables (Relevant)
- `sessions`: session metadata + status
- `audio_files`: uploaded audio, linked to sessions
- `transcripts`: merged transcript + diarization
- `audio_chunks`: chunk metadata (order + offsets)
- `chunk_transcripts`: per-chunk transcript + diarization
- `session_notes`: structured notes output
