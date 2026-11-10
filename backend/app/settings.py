"""Reads and writes the .env file from the Settings page."""
import os
import re
import tempfile

from . import config

SECRET_KEYS = {
    "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY",
    "DEEPSEEK_API_KEY", "MISTRAL_API_KEY", "OPENAI_COMPAT_API_KEY", "ELEVENLABS_API_KEY", "PIXABAY_API_KEY",
    "PEXELS_API_KEY", "TMDB_API_KEY", "META_ACCESS_TOKEN",
}
TOGGLE_KEYS = {"OFFICIAL_CLIPS_SHORTS", "PUBLISH_YOUTUBE", "PUBLISH_INSTAGRAM", "PUBLISH_FACEBOOK", "OFFICIAL_CLIPS", "HOOK_SFX", "TREND_RESEARCH", "HW_ENCODE", "HOOK_ENABLED", "BUDGET_MODE", "RANK_THUMBNAILS", "VOICE_FALLBACK", "DESCRIBE_TRAILER_SCENES", "SHORT_PAN", "PREFER_VERTICAL_TRAILERS", "SHORT_THUMBNAILS"}
NUMBER_KEYS = {"SHORT_SHOT_SECONDS", "LONG_SHOT_SECONDS", "SHORT_MAX_SECONDS", "SINGLE_MAX_SECONDS", "LONG_MAX_SECONDS", "TRAILER_MAX_HEIGHT", "SINGLE_TARGET_WORDS", "SINGLE_MAX_WORDS", "HOOK_SECONDS", "MUSIC_VOLUME", "VOICE_LUFS", "ELEVENLABS_STABILITY", "SHORT_FILL", "SHORT_TARGET_WORDS", "SHORT_MAX_WORDS",
               "LONG_TARGET_WORDS", "LONG_MAX_WORDS", "GEMINI_DAILY_LIMIT", "YOUTUBE_DAILY_UPLOADS", "WORKER_THREADS",
               "GEMINI_TIMEOUT"}
TEXT_KEYS = {
    "YT_PRIVACY", "MUSIC_SOURCE", "FB_PAGE_ID", "IG_USER_ID", "META_GRAPH_VERSION", "CLIP_RES", "EDGE_VOICE_FEMALE",
    "SHORT_SEGMENTS", "LONG_SEGMENTS", "SINGLE_SEGMENTS", "OUTPUT_RES_SHORT", "OUTPUT_RES_LONG", "HOOK_STYLE",
    "LLM_PROVIDERS", "GEMINI_MODEL", "GEMINI_FALLBACK_MODELS", "ANTHROPIC_MODEL", "ANTHROPIC_VISION_MODEL",
    "OPENAI_MODEL", "XAI_MODEL", "GROQ_MODEL", "OPENROUTER_MODEL", "DEEPSEEK_MODEL", "MISTRAL_MODEL",
    "OPENAI_COMPAT_MODEL", "OPENAI_COMPAT_BASE_URL", "VOICE_PROVIDER", "EDGE_VOICE", "ELEVENLABS_VOICE_ID",
    "ELEVENLABS_MODEL", "OPENAI_TTS_MODEL", "OPENAI_TTS_VOICE", "OPENAI_IMAGE_MODEL",
}
ALLOWED = SECRET_KEYS | TOGGLE_KEYS | NUMBER_KEYS | TEXT_KEYS


def mask(v: str) -> str:
    return "" if not v else ("••••" + v[-4:] if len(v) > 8 else "••••")


def current():
    """Non-secret values as strings, plus masked secrets."""
    vals, secrets = {}, {}
    for k in sorted(ALLOWED):
        v = os.getenv(k, "").strip()
        if k in SECRET_KEYS:
            secrets[k] = mask(v)
        else:
            vals[k] = v
    return {"values": vals, "secrets": secrets}


def _clean(key, value):
    value = str(value).strip().replace("\r", "").replace("\n", "")
    if key in TOGGLE_KEYS:
        return "1" if value.lower() in ("1", "true", "yes", "on") else "0"
    if key in NUMBER_KEYS and value != "":
        try:
            float(value)
        except ValueError:
            raise ValueError(f"{key} must be a number.")
    if key == "VOICE_PROVIDER" and value not in ("edge", "elevenlabs", "openai"):
        raise ValueError("VOICE_PROVIDER must be edge, elevenlabs or openai.")
    if key in ("OUTPUT_RES_SHORT", "OUTPUT_RES_LONG") and value.lower() not in ("1080p", "1440p", "4k"):
        raise ValueError(f"{key} must be 1080p, 1440p or 4k.")
    if key == "YT_PRIVACY" and value.lower() not in ("private", "unlisted", "public"):
        raise ValueError("YT_PRIVACY must be private, unlisted or public.")
    if key == "MUSIC_SOURCE" and value.lower() not in ("auto", "library", "generated"):
        raise ValueError("MUSIC_SOURCE must be auto, library or generated.")
    if key == "CLIP_RES" and value.lower() not in ("1080p", "match"):
        raise ValueError("CLIP_RES must be 1080p or match.")
    if key == "TRAILER_MAX_HEIGHT" and value not in ("1080", "1440", "2160"):
        raise ValueError("TRAILER_MAX_HEIGHT must be 1080, 1440 or 2160.")
    if key == "HOOK_STYLE" and value.lower() not in ("auto", "balanced", "romance", "action", "shock", "comedy", "emotional"):
        raise ValueError("HOOK_STYLE must be auto, balanced, romance, action, shock, comedy or emotional.")
    if key == "LLM_PROVIDERS":
        ids = [x.strip().lower() for x in value.split(",") if x.strip()]
        bad = [x for x in ids if x not in config.PROVIDERS]
        if bad:
            raise ValueError(f"Unknown AI provider: {', '.join(bad)}")
        value = ",".join(ids)
    return value


def save(values: dict, clear=()):
    """Update keys in .env (keeping comments and other lines), then reload the settings."""
    updates = {}
    for k, v in (values or {}).items():
        if k not in ALLOWED:
            raise ValueError(f"Unknown setting {k}.")
        updates[k] = _clean(k, v)
    for k in clear or []:
        if k in SECRET_KEYS:
            updates[k] = ""
    lines = config.ENV_FILE.read_text(encoding="utf-8").splitlines() if config.ENV_FILE.exists() else []
    seen = set()
    for i, line in enumerate(lines):
        m = re.match(r"^\s*([A-Z0-9_]+)\s*=", line)
        if m and m.group(1) in updates:
            lines[i] = f"{m.group(1)}={updates[m.group(1)]}"
            seen.add(m.group(1))
    for k, v in updates.items():
        if k not in seen:
            lines.append(f"{k}={v}")
    fd, tmp = tempfile.mkstemp(dir=str(config.ENV_FILE.parent), prefix=".env.", text=True)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, config.ENV_FILE)
    for k, v in updates.items():  # make the change visible right away
        os.environ[k] = v
    config.reload()
    return list(updates)


def _rules_path(kind="multi"):
    return {"single": config.SCRIPT_RULES_SINGLE_FILE, "long": config.SCRIPT_RULES_LONG_FILE}.get(kind, config.SCRIPT_RULES_FILE)


def get_rules(kind="multi") -> str:
    try:
        return _rules_path(kind).read_text(encoding="utf-8")
    except OSError:
        return ""


def save_rules(text: str, kind="multi"):
    _rules_path(kind).write_text((text or "").strip() + "\n", encoding="utf-8")
