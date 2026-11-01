import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)
PORT = 8810
from pathlib import Path
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import ai_client
from core_config.core_config import Settings
from api_routes import create_app
import uvicorn

DATA = Path(HERE) / "data"
(DATA / "audio").mkdir(parents=True, exist_ok=True)
(DATA / "images").mkdir(parents=True, exist_ok=True)

_orig_demo = ai_client.generate_demo_song

def _demo(prompt="", genre=None, mood=None, lyrics=None, title=None, **kw):
    s = Settings()
    s.AUDIO_DIR = DATA / "audio"
    s.IMAGE_DIR = DATA / "images"
    res = _orig_demo(prompt=prompt, genre=genre, mood=mood, lyrics=lyrics, title=title, settings=s)
    res["audio_path"] = "/media/audio/" + Path(res["audio_path"]).name
    res["image_path"] = "/media/images/" + Path(res["image_path"]).name
    return res

ai_client.generate_demo_song = _demo

import asyncio, inspect
_orig_gen = ai_client.AIClient.generate_song

def _gen_sync(self, *a, **k):
    r = _orig_gen(self, *a, **k)
    if inspect.isawaitable(r):
        r = asyncio.run(r)
    if isinstance(r, dict):
        for key, folder in (("audio_path", "audio"), ("image_path", "images")):
            v = r.get(key)
            if v and not str(v).startswith("/media"):
                r[key] = "/media/%s/%s" % (folder, Path(str(v)).name)
    return r

ai_client.AIClient.generate_song = _gen_sync

# ---- ACE-Step bridge: real local song generation, persistent history, unlimited quota ----
import json, re, shutil, threading, time, urllib.request, urllib.parse, uuid, datetime
import songs_service, api_routes
import songs_service.songs_service as ss

ACE = "http://127.0.0.1:8001"
CFG = {"seconds": int(os.environ.get("MELODY_SECONDS", "300"))}
_GPU = threading.Lock()
HIST = DATA / "history.json"

def _post(path, body):
    req = urllib.request.Request(ACE + path, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))

def _lang(text):
    if re.search(r"[\u0B80-\u0BFF]", text or ""): return "ta"
    if re.search(r"[\u0900-\u097F]", text or ""): return "hi"
    return "en"

def _ace_generate(prompt, genre, mood, lyrics):
    style = ", ".join([x for x in [genre, mood, prompt] if x]) or "pop song"
    lyr = (lyrics or "").strip()
    body = {"prompt": style, "lyrics": lyr if lyr else "[Instrumental]", "audio_duration": CFG["seconds"],
            "vocal_language": _lang(lyr) if lyr else "en", "thinking": False, "audio_format": "wav"}
    r = _post("/release_task", body)
    d = r.get("data") or r
    tid = d.get("task_id")
    if not tid: raise RuntimeError("ACE-Step gave no task id: %s" % r)
    t0 = time.time()
    while time.time() - t0 < 1800:
        time.sleep(5)
        q = _post("/query_result", {"task_id_list": json.dumps([tid])})
        item = (q.get("data") or [{}])[0]
        st = item.get("status")
        if st == 1:
            res = json.loads(item["result"])[0]
            qs = urllib.parse.urlparse(res["file"]).query
            return urllib.parse.parse_qs(qs)["path"][0]
        if st == 2:
            raise RuntimeError("ACE-Step failed: %s" % str(item.get("result"))[:300])
    raise RuntimeError("ACE-Step timeout")

def _run_task(song_id, prompt="", genre="", mood="", lyrics="", title=""):
    try:
        with _GPU:
            src = _ace_generate(prompt, genre, mood, lyrics)
        name = song_id + ".wav"
        shutil.copyfile(src, str(DATA / "audio" / name))
        songs_service.update_song(song_id, status="completed", audio_path="/media/audio/" + name, image_path="")
    except Exception as e:
        with open(os.path.join(HERE, "melody_err.log"), "a", encoding="utf-8") as f:
            f.write("%s ACE-Step error: %s\n" % (datetime.datetime.now(), e))
        songs_service.update_song(song_id, status="failed", title=(title or "Song") + " (failed - see melody_err.log)")
    _save()

import api_routes.api_routes as _ar
_ar._run_generation_task = _run_task

# unlimited quota (local engine, no per-song cost)
def _q():
    n = len([s for s in ss._IN_MEMORY_SONGS.values()])
    return ss.QuotaData({"id": "local", "date": "", "count": n, "max_quota": 999999, "remaining": 999999, "limit": "unlimited"})
for _m in (songs_service, ss):
    _m.get_quota = lambda *a, **k: _q()
    _m.check_quota = lambda *a, **k: True
    _m.increment_quota = lambda *a, **k: _q()

# persistent history
def _save():
    try:
        HIST.write_text(json.dumps(list(ss._IN_MEMORY_SONGS.values()), ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

def _load():
    try:
        for s in json.loads(HIST.read_text(encoding="utf-8")):
            if s.get("status") == "generating":
                s["status"] = "failed"; s["title"] = s.get("title", "Song") + " (interrupted)"
            ss._IN_MEMORY_SONGS[s["id"]] = ss.SongData(s)
    except Exception:
        pass

for _n in ("create_song", "update_song", "delete_song", "toggle_like"):
    def _wrap(fn):
        def w(*a, **k):
            r = fn(*a, **k); _save(); return r
        return w
    _w = _wrap(getattr(ss, _n))
    setattr(ss, _n, _w); setattr(songs_service, _n, _w)
_load()
# ---- end bridge ----
app = create_app()
app.mount("/media", StaticFiles(directory=str(DATA)), name="media")

_JS = """playSong(song) {
                    this.currentSong = song;
                    this.isPlaying = true;
                    if (window.__au) { window.__au.pause(); }
                    const a = new Audio(song.audio_path);
                    window.__au = a;
                    a.volume = parseFloat(this.volume);
                    a.onloadedmetadata = () => { this.duration = a.duration; };
                    a.ontimeupdate = () => { this.currentTime = a.currentTime; };
                    a.onended = () => { this.isPlaying = false; };
                    a.play().catch(e => { console.error(e); this.isPlaying = false; });
                },

                togglePlay() {
                    const a = window.__au;
                    if (!a) return;
                    if (a.paused) { a.play(); } else { a.pause(); }
                    this.isPlaying = !a.paused;
                },

                stopPlayer() {
                    if (window.__au) { window.__au.pause(); window.__au.currentTime = 0; }
                    this.isPlaying = false;
                    this.currentSong = null;
                },

                updateVolume() {
                    if (window.__au) { window.__au.volume = parseFloat(this.volume); }
                },

                """

@app.get("/api/mp3/{song_id}")
def song_mp3(song_id: str):
    import subprocess, imageio_ffmpeg
    from fastapi import HTTPException
    s = ss._IN_MEMORY_SONGS.get(song_id)
    if not s:
        raise HTTPException(404, "song not found")
    wav = DATA / "audio" / (song_id + ".wav")
    mp3 = DATA / "audio" / (song_id + ".mp3")
    if not wav.exists():
        raise HTTPException(404, "audio file missing")
    if not mp3.exists():
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "320k", str(mp3)], check=True)
    name = re.sub(r'[^A-Za-z0-9 _-]+', '', s.get("title") or "song").strip() or "song"
    return FileResponse(str(mp3), media_type="audio/mpeg", filename=name + ".mp3")

@app.get("/api/duration")
def get_duration():
    return {"seconds": CFG["seconds"]}

@app.post("/api/duration/{secs}")
def set_duration(secs: int):
    CFG["seconds"] = max(10, min(300, secs))
    return {"seconds": CFG["seconds"]}

_SEL = """<div class="mb-3"><label class="block text-xs font-semibold text-slate-400 mb-1">Song length</label>
<select id="songlen" class="w-full bg-slate-800 border border-slate-700 rounded-lg p-2 text-sm text-slate-200">
<option value="30">30 sec</option><option value="60">1 min</option><option value="90">1.5 min</option><option value="120">2 min</option><option value="150">2.5 min</option><option value="180">3 min</option><option value="210">3.5 min</option><option value="240">4 min</option><option value="300" selected>5 min</option></select></div>
<script>(function(){var s=document.getElementById('songlen');fetch('/api/duration').then(r=>r.json()).then(j=>{s.value=String(j.seconds)});s.addEventListener('change',function(){fetch('/api/duration/'+s.value,{method:'POST'});});})();</script>
"""

@app.get("/")
def index():
    from fastapi.responses import HTMLResponse
    html = open(os.path.join(HERE, "frontend_ui", "index.html"), encoding="utf-8").read()
    a = html.find("playSong(song) {")
    b = html.find("formatTime(seconds) {")
    if a != -1 and b != -1 and a < b:
        html = html[:a] + _JS + html[b:]
    k = html.find('<button type="submit"')
    if k != -1:
        html = html[:k] + _SEL + html[k:]
    from ui_patch import patch
    html = patch(html)
    return HTMLResponse(html)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT)


