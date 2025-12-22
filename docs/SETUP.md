# Setup and Run Commands

```bash
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
uvicorn my_project.main:app --reload --app-dir src
```

# Test Upload Command

```bash
curl -F "file=@/path/to/audio.wav" http://127.0.0.1:8000/upload
```

# Run the UI

```bash
cd docs/web
python3 -m http.server 5173
```

Then open `http://127.0.0.1:5173` in a browser.
