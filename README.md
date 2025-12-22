# My Project

FastAPI service for ingesting audio files, plus a lightweight React UI in `src/web`.

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
uvicorn server.main:app --reload --app-dir src
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
