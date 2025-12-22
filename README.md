# My Project

FastAPI service for ingesting audio files, plus a lightweight React UI in `src/web`.

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
uvicorn my_project.main:app --reload --app-dir src
```

## UI (React)

```bash
cd src/web
python3 -m http.server 5173
```

Open `http://127.0.0.1:5173`.
