import json
import re
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, db, llm, movies as movie_utils, settings as settings_mod, worker
from .pipeline import assets as assets_mod
from .pipeline import social, youtube

app = FastAPI(title="YT Studio")
db.init()


@app.on_event("startup")
def _startup():
    worker.start()


def _channels():
    try:
        return json.loads(config.CHANNELS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


class JobIn(BaseModel):
    mode: str = "title"            # "title" or "link"
    title: str = ""
    url: str = ""
    channel_id: str = ""
    format: str = "short"          # "short" or "long"
    language: str = ""
    voice_id: str = ""
    use_pexels: bool = True
    rights_confirmed: bool = False
    use_trailers: bool = True
    unique_movies: bool = True
    movie_count: str = "auto"      # auto | one | many
    voice_provider: str = ""      # "" = use .env, "edge" (free) or "elevenlabs"


class MetaIn(BaseModel):
    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    selected_thumbnail: str | None = None
    instagram_caption: str | None = None
    facebook_title: str | None = None
    facebook_description: str | None = None


class UploadIn(BaseModel):
    privacy: str = "private"       # private | unlisted | public


@app.get("/api/usage")
def usage():
    import requests as rq
    f_short, f_long = config.FORMATS["short"], config.FORMATS["long"]
    chars = {"short": int(f_short["target_words"] * 6.5), "long": int(f_long["target_words"] * 6.5)}
    # measured average AI requests per finished video (falls back to a guess until there are some)
    meas = {"short": [], "long": []}
    for j in db.list_jobs(60):
        r = j.get("result") or {}
        if j["status"] in ("review", "uploaded") and r.get("ai_requests") is not None and r.get("format") in meas:
            meas[r["format"]].append(r["ai_requests"])
    guess = {"short": 6 if config.BUDGET_MODE else 12, "long": 9 if config.BUDGET_MODE else 14}
    per_video = {k: (round(sum(v) / len(v), 1) if v else guess[k]) for k, v in meas.items()}
    gem_per = per_video["short"]
    out = {"day": db.today(),
           "gemini": {"used_today": db.total_ai_requests(), "limit": config.GEMINI_DAILY_LIMIT or None,
                      "per_video": gem_per, "per_video_by_format": per_video,
                      "measured": {k: len(v) for k, v in meas.items()}},
           "youtube": {"used_today": db.get_usage("youtube_uploads"), "limit": config.YOUTUBE_DAILY_UPLOADS},
           "elevenlabs": {"used_today": db.get_usage("elevenlabs_chars"), "active": config.VOICE_PROVIDER == "elevenlabs",
                          "chars_per_video": chars},
           "voice_provider": config.VOICE_PROVIDER}
    if config.ELEVENLABS_API_KEY:
        try:
            r = rq.get("https://api.elevenlabs.io/v1/user/subscription", headers={"xi-api-key": config.ELEVENLABS_API_KEY}, timeout=15)
            if r.status_code == 200:
                j = r.json()
                out["elevenlabs"].update({"used": j.get("character_count"), "limit": j.get("character_limit"),
                                          "remaining": (j.get("character_limit") or 0) - (j.get("character_count") or 0),
                                          "resets_unix": j.get("next_character_count_reset_unix"), "tier": j.get("tier")})
            else:
                out["elevenlabs"]["error"] = ("This API key cannot read the balance (give it 'User: Read' permission in ElevenLabs), "
                                              "or the key is wrong." if r.status_code in (401, 403) else f"HTTP {r.status_code}")
        except Exception as e:
            out["elevenlabs"]["error"] = f"Could not reach ElevenLabs: {type(e).__name__}"
    # how many more videos today, per format: the smallest of the limits that apply
    est = {}
    for fmt in ("short", "long"):
        caps = {}
        if out["gemini"]["limit"]:
            caps["AI requests"] = max(0, int((out["gemini"]["limit"] - out["gemini"]["used_today"]) // max(1, per_video[fmt])))
        caps["YouTube uploads"] = max(0, out["youtube"]["limit"] - out["youtube"]["used_today"])
        if config.VOICE_PROVIDER == "elevenlabs" and out["elevenlabs"].get("remaining") is not None:
            caps["ElevenLabs credits"] = max(0, out["elevenlabs"]["remaining"] // chars[fmt])
        limiting = min(caps, key=caps.get)
        est[fmt] = {"videos": caps[limiting], "limited_by": limiting, "all": caps}
    out["estimate"] = est
    return out


@app.get("/api/config")
def get_config():
    return {
        "instagram": social.status()["instagram"], "facebook": social.status()["facebook"],
        "llm": llm.available(),
        "providers": [{"id": k, "label": v["label"], "ready": config.provider_ready(k)} for k, v in config.PROVIDERS.items()],
        "llm_label": llm.label(),
        "voice": config.VOICE_PROVIDER == "edge" or bool(config.OPENAI_API_KEY if config.VOICE_PROVIDER == "openai" else config.ELEVENLABS_API_KEY),
        "voice_label": {"edge": "Edge voice (free)", "openai": "ChatGPT voice"}.get(config.VOICE_PROVIDER, "ElevenLabs"),
        "stock": bool(config.PEXELS_API_KEY or config.PIXABAY_API_KEY),
        "openai_images": bool(config.OPENAI_API_KEY),
        "youtube_connected": youtube.is_connected(),
        "defaults": {"youtube": config.PUBLISH_YOUTUBE, "instagram": config.PUBLISH_INSTAGRAM, "facebook": config.PUBLISH_FACEBOOK},
        "yt_privacy": config.YT_PRIVACY,
        "channels": _channels(),
    }


@app.post("/api/jobs")
def create_job(body: JobIn):
    if body.format not in config.FORMATS:
        raise HTTPException(400, "format must be 'short' or 'long'")
    if body.mode == "title" and not body.title.strip():
        raise HTTPException(400, "Enter a video title.")
    if body.mode == "link":
        if not re.match(r"^https?://", body.url.strip()):
            raise HTTPException(400, "Enter a valid video link.")
        if not body.rights_confirmed:
            raise HTTPException(400, "Confirm that you own this video or have permission to reuse it.")
    if body.voice_provider not in ("", "edge", "elevenlabs", "openai"):
        raise HTTPException(400, "voice_provider must be edge, elevenlabs or openai")
    if body.movie_count not in ("auto", "one", "many"):
        raise HTTPException(400, "movie_count must be auto, one or many")
    if body.mode not in ("title", "link"):
        raise HTTPException(400, "mode must be 'title' or 'link'")
    channel = next((c for c in _channels() if c["id"] == body.channel_id), {})
    inp = body.model_dump()
    inp["channel"] = channel
    job_id = db.create_job(inp)
    worker.enqueue(job_id)
    return {"id": job_id}


@app.get("/api/jobs")
def list_jobs():
    return db.list_jobs()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    j = db.get_job(job_id)
    if not j:
        raise HTTPException(404, "Job not found")
    return j


@app.post("/api/jobs/{job_id}/retry")
def retry(job_id: str):
    j = db.get_job(job_id)
    if not j:
        raise HTTPException(404, "Job not found")
    if j["status"] not in ("failed", "review"):
        raise HTTPException(400, "Only failed or finished jobs can be re-run.")
    db.update_job(job_id, status="queued", stage="Waiting in queue", progress=0, error="")
    worker.enqueue(job_id)
    return {"ok": True}


@app.patch("/api/jobs/{job_id}/metadata")
def edit_meta(job_id: str, body: MetaIn):
    j = db.get_job(job_id)
    if not j or not j["result"]:
        raise HTTPException(404, "Job not ready")
    r = j["result"]
    for k in ("title", "description", "tags", "instagram_caption", "facebook_title", "facebook_description"):
        v = getattr(body, k)
        if v is not None:
            r["metadata"][k] = v
    if body.selected_thumbnail:
        r["selected_thumbnail"] = body.selected_thumbnail
    db.update_job(job_id, result=r)
    return r


@app.post("/api/jobs/{job_id}/upload")
def upload(job_id: str, body: UploadIn):
    j = db.get_job(job_id)
    if not j or j["status"] not in ("review", "uploaded"):
        raise HTTPException(400, "Job is not ready to upload.")
    if body.privacy not in ("private", "unlisted", "public"):
        raise HTTPException(400, "Invalid privacy value.")
    r = j["result"]
    work = config.JOBS_DIR / job_id
    try:
        res = youtube.upload(
            work / r["video"], r["metadata"]["title"], r["metadata"]["description"], r["metadata"]["tags"],
            privacy=body.privacy, thumbnail=(work / "thumbs" / r["selected_thumbnail"]) if r.get("selected_thumbnail") else None,
            is_short=r["format"] == "short",
        )
    except Exception as e:
        raise HTTPException(400, str(e))
    r["upload"] = {**res, "privacy": body.privacy}
    db.update_job(j["id"], status="uploaded", stage="Uploaded", result=r)
    return r["upload"]


class PublishIn(BaseModel):
    platforms: list = ["youtube"]
    privacy: str = "private"       # YouTube only


@app.post("/api/jobs/{job_id}/publish")
def publish(job_id: str, body: PublishIn):
    """One click: YouTube, Instagram and Facebook, each with its own title/caption. One platform failing does not stop the others."""
    j = db.get_job(job_id)
    if not j or j["status"] not in ("review", "uploaded"):
        raise HTTPException(400, "Job is not ready to publish.")
    if body.privacy not in ("private", "unlisted", "public"):
        raise HTTPException(400, "Invalid privacy value.")
    r, work = j["result"], config.JOBS_DIR / job_id
    m, fmt = r["metadata"], r["format"]
    video, copy, results = work / r["video"], None, {}
    for p in body.platforms:
        try:
            if p == "youtube":
                res = youtube.upload(video, m["title"], m["description"], m["tags"], privacy=body.privacy,
                                     thumbnail=(work / "thumbs" / r["selected_thumbnail"]) if r.get("selected_thumbnail") else None,
                                     is_short=fmt == "short")
            elif p in ("instagram", "facebook"):
                if p == "instagram" and fmt != "short":
                    raise RuntimeError("Instagram Reels are vertical and short, so long landscape videos are not sent to Instagram.")
                if copy is None:  # a lighter 1080p copy is quicker to upload and fits their limits
                    copy = social.make_social_copy(video, work / "social_1080.mp4", fmt == "short")
                res = (social.publish_instagram(copy, m.get("instagram_caption") or m["description"], fmt) if p == "instagram" else
                       social.publish_facebook(copy, m.get("facebook_title") or m["title"], m.get("facebook_description") or m["description"], fmt))
            else:
                raise RuntimeError("Unknown platform")
            results[p] = {"ok": True, **res}
        except Exception as e:
            results[p] = {"ok": False, "error": str(e)[:500]}
    published = r.get("published") or {}
    for p, v in results.items():
        if v["ok"]:
            published[p] = {k: x for k, x in v.items() if k != "ok"}
    r["published"] = published
    if "youtube" in published:
        r["upload"] = {**published["youtube"], "privacy": body.privacy}
    if published:
        db.update_job(job_id, status="uploaded", stage="Published", result=r)
    return results


@app.get("/api/youtube/status")
def yt_status():
    return youtube.state()


@app.post("/api/youtube/secret")
async def yt_secret(file: UploadFile = File(...)):
    raw = await file.read()
    try:
        j = json.loads(raw)
    except Exception:
        raise HTTPException(400, "That is not a valid JSON file.")
    if "installed" not in j:
        raise HTTPException(400, "This is a Web-app client. In Google Cloud, create an OAuth client of type 'Desktop app' and download that file."
                            if "web" in j else "This does not look like a Google client_secret.json file.")
    config.CLIENT_SECRET.write_bytes(raw)
    return youtube.state()


@app.post("/api/youtube/connect")
def yt_connect():
    try:
        youtube.start_connect()
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    return youtube.state()


@app.post("/api/youtube/disconnect")
def yt_disconnect():
    youtube.disconnect()
    return youtube.state()


@app.post("/api/test/social")
def test_social():
    return social.test_connection()


# ---- asset library -------------------------------------------------------
@app.get("/api/library")
def library():
    return [{**a, "name": Path(a["path"]).name} for a in assets_mod.scan_library()]


@app.post("/api/library")
async def add_library(file: UploadFile = File(...), description: str = Form(""), license: str = Form("own")):
    ext = Path(file.filename).suffix.lower()
    if ext not in assets_mod.VIDEO_EXT | assets_mod.IMAGE_EXT:
        raise HTTPException(400, "Upload a video (mp4, mov, mkv, webm) or an image (jpg, png, webp).")
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", file.filename)
    dest = config.LIBRARY / safe
    with dest.open("wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)
    dest.with_suffix(".json").write_text(json.dumps({"description": description, "license": license}))
    return {"ok": True, "name": safe}


@app.delete("/api/library/{name}")
def delete_library(name: str):
    p = config.LIBRARY / Path(name).name
    if p.exists():
        p.unlink()
        p.with_suffix(".json").unlink(missing_ok=True)
    return {"ok": True}


# ---- settings, tests, stats -----------------------------------------------
class SettingsIn(BaseModel):
    values: dict = {}
    clear: list = []
    script_rules: str | None = None
    script_rules_single: str | None = None
    script_rules_long: str | None = None


class ProviderIn(BaseModel):
    provider: str


@app.get("/api/settings")
def get_settings():
    cur = settings_mod.current()
    provs = []
    for pid, p in config.PROVIDERS.items():
        provs.append({"id": pid, "label": p["label"], "free": bool(p.get("free")), "kind": p["kind"],
                      "key_name": p["key"], "model_name": p["model"], "base_env": p.get("base_env"),
                      "ready": config.provider_ready(pid), "has_key": bool(config.env(p["key"]))})
    return {**cur, "providers": provs, "order": config.LLM_PROVIDERS, "script_rules": settings_mod.get_rules(), "script_rules_single": settings_mod.get_rules("single"), "script_rules_long": settings_mod.get_rules("long"),
            "env_exists": config.ENV_FILE.exists()}


@app.post("/api/settings")
def save_settings(body: SettingsIn):
    try:
        changed = settings_mod.save(body.values, body.clear)
        if body.script_rules is not None:
            settings_mod.save_rules(body.script_rules)
        if body.script_rules_single is not None:
            settings_mod.save_rules(body.script_rules_single, "single")
        if body.script_rules_long is not None:
            settings_mod.save_rules(body.script_rules_long, "long")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"saved": changed}


@app.post("/api/test/ai")
def test_ai(body: ProviderIn):
    if body.provider not in config.PROVIDERS:
        raise HTTPException(400, "Unknown provider")
    return llm.ping(body.provider)


@app.get("/api/models/{provider}")
def models(provider: str):
    if provider not in config.PROVIDERS:
        raise HTTPException(404, "Unknown provider")
    try:
        return {"models": llm.list_models(provider)}
    except Exception as e:
        raise HTTPException(400, str(e)[:300])


@app.post("/api/test/voice")
def test_voice():
    import time as _t
    from .pipeline import voice as voice_mod
    out_dir = config.JOBS_DIR / "_test"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / "voice.mp3"
    text = "The detective opened the door, and the whole story changed."
    try:
        prov = config.VOICE_PROVIDER
        if prov == "edge":
            voice_mod._tts_edge(text, config.EDGE_VOICE, out)
        elif prov == "openai":
            voice_mod._tts_openai(text, config.OPENAI_TTS_VOICE, out, "dramatic")
        else:
            if not config.ELEVENLABS_API_KEY:
                return {"ok": False, "error": "Add your ElevenLabs API key first."}
            voice_mod._tts_eleven("[serious] " + text if config.ELEVENLABS_MODEL.startswith(("eleven_v3", "eleven_v4")) else text,
                                  config.ELEVENLABS_VOICE_ID, out)
        return {"ok": True, "url": f"/files/_test/voice.mp3?t={int(_t.time())}", "provider": prov}
    except Exception as e:
        return {"ok": False, "error": str(e)[:400]}


@app.get("/api/stats")
def stats():
    jobs = db.list_jobs(500)
    done = [j for j in jobs if j["status"] in ("review", "uploaded") and j.get("result")]
    return {"videos": len(done), "uploaded": sum(1 for j in done if j["status"] == "uploaded"),
            "minutes": round(sum(j["result"].get("duration", 0) for j in done) / 60, 1),
            "movies": len(db.used_movies()), "running": sum(1 for j in jobs if j["status"] in ("running", "queued"))}


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    import shutil
    j = db.get_job(job_id)
    if not j:
        raise HTTPException(404, "Job not found")
    if j["status"] in ("running", "queued"):
        raise HTTPException(400, "Wait for the job to finish before deleting it.")
    db.delete_used_for_job(job_id)
    db.delete_job(job_id)
    shutil.rmtree(config.JOBS_DIR / job_id, ignore_errors=True)
    return {"ok": True}


# ---- movies already used --------------------------------------------------
class UsedIn(BaseModel):
    text: str


@app.get("/api/used-movies")
def get_used():
    return db.used_movies()


@app.post("/api/used-movies")
def add_used(body: UsedIn):
    parsed = [movie_utils.parse_line(l) for l in body.text.splitlines()]
    items = [{"title": t, "year": y} for t, y in (x for x in parsed if x)]
    existing = db.used_movies()
    new = [m for m in items if not any(movie_utils.same_movie(m["title"], m["year"], u["title"], u["year"]) for u in existing)]
    db.add_used_movies(new, "manual")
    return {"added": len(new), "skipped": len(items) - len(new)}


@app.delete("/api/used-movies/{movie_id}")
def remove_used(movie_id: int):
    db.delete_used_movie(movie_id)
    return {"ok": True}


# ---- static --------------------------------------------------------------
app.mount("/files", StaticFiles(directory=str(config.JOBS_DIR)), name="files")
STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


