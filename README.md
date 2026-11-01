# AI Melody Studio

A text-to-song web app: describe a song (prompt, genre, mood, optional lyrics) and generate audio, then play, like, download (MP3/WAV) and browse your song history.

## How generation works
- `run_melody.py` (the launcher) sends generation jobs to a locally running
  [ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5) API server at `http://127.0.0.1:8001`.
  ACE-Step is an open-source music generation model (MIT License) by the ACE-Step team; it is **not** included here – install and start it separately.
- The `ai_client` module also contains an optional Gemini-API path (reads `GEMINI_API_KEY` from the environment) and a demo generator that produces placeholder audio when no backend is configured.
- Song length is selectable (30 s – 5 min). MP3 export uses `imageio-ffmpeg`.

## Structure
`core_config/`, `ai_client/`, `songs_service/`, `storage_manager/`, `database_schema/`, `api_routes/` (FastAPI), `frontend_ui/` (HTML UI), `run_melody.py`, `ui_patch.py`.

## Run
```bash
pip install fastapi uvicorn imageio-ffmpeg
# start an ACE-Step 1.5 API server on port 8001 first
python run_melody.py   # http://127.0.0.1:8810
```
Generated audio and history are stored in `data/` (git-ignored).

## Tests
```bash
pip install pytest pytest-asyncio httpx
python -m pytest
```

## License
MIT. ACE-Step is a separate project under its own license.
