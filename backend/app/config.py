"""All settings. They come from the .env file and can be changed from the Settings page without restarting:
reload() re-reads .env and updates every value below."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env"

STORAGE = ROOT / "storage"
JOBS_DIR = STORAGE / "jobs"
ASSET_DIR = ROOT / "assets"
LIBRARY = ASSET_DIR / "library"
MUSIC = ASSET_DIR / "music"
TRAILERS = ASSET_DIR / "trailers"
DB_PATH = STORAGE / "studio.db"
CHANNELS_FILE = ROOT / "channels.json"
SCRIPT_RULES_FILE = ROOT / "script_rules.txt"
SCRIPT_RULES_SINGLE_FILE = ROOT / "script_rules_single.txt"
SCRIPT_RULES_LONG_FILE = ROOT / "script_rules_long.txt"
CLIENT_SECRET = ROOT / "client_secret.json"
TOKEN_FILE = ROOT / "token.json"

for _p in (STORAGE, JOBS_DIR, LIBRARY, MUSIC, TRAILERS):
    _p.mkdir(parents=True, exist_ok=True)


def env(name, default=""):
    return os.getenv(name, default).strip()


def _num(name, default, cast=float):
    try:
        return cast(env(name, str(default)) or default)
    except ValueError:
        return cast(default)


def _flag(name, default="0"):
    return env(name, default).lower() in ("1", "true", "yes", "on")


def _csv(name):
    return [x.strip() for x in env(name).split(",") if x.strip()]


# AI text providers. "kind" decides how we talk to them. Models are NOT hard-coded for most providers because
# names change often: pick one in Settings (the page can list the models your key can use).
PROVIDERS = {
    "gemini":     {"label": "Gemini (Google)",   "kind": "gemini",    "key": "GEMINI_API_KEY",       "model": "GEMINI_MODEL",       "free": True},
    "anthropic":  {"label": "Claude (Anthropic)", "kind": "anthropic", "key": "ANTHROPIC_API_KEY",    "model": "ANTHROPIC_MODEL"},
    "openai":     {"label": "ChatGPT (OpenAI)",  "kind": "compat",    "key": "OPENAI_API_KEY",       "model": "OPENAI_MODEL",       "base": "https://api.openai.com/v1"},
    "xai":        {"label": "Grok (xAI)",        "kind": "compat",    "key": "XAI_API_KEY",          "model": "XAI_MODEL",          "base": "https://api.x.ai/v1"},
    "groq":       {"label": "Groq",              "kind": "compat",    "key": "GROQ_API_KEY",         "model": "GROQ_MODEL",         "base": "https://api.groq.com/openai/v1", "free": True},
    "openrouter": {"label": "OpenRouter",        "kind": "compat",    "key": "OPENROUTER_API_KEY",   "model": "OPENROUTER_MODEL",   "base": "https://openrouter.ai/api/v1", "free": True},
    "deepseek":   {"label": "DeepSeek",          "kind": "compat",    "key": "DEEPSEEK_API_KEY",     "model": "DEEPSEEK_MODEL",     "base": "https://api.deepseek.com/v1"},
    "mistral":    {"label": "Mistral",           "kind": "compat",    "key": "MISTRAL_API_KEY",      "model": "MISTRAL_MODEL",      "base": "https://api.mistral.ai/v1"},
    "custom":     {"label": "Custom (any OpenAI-style API)", "kind": "compat", "key": "OPENAI_COMPAT_API_KEY", "model": "OPENAI_COMPAT_MODEL", "base_env": "OPENAI_COMPAT_BASE_URL"},
}


def provider_base(name):
    p = PROVIDERS[name]
    return (env(p["base_env"]) if "base_env" in p else p["base"]).rstrip("/")


def _load():
    g = globals()
    # ---- AI providers, tried in this order. LLM_PROVIDERS wins; the older two settings still work.
    order = [x.lower() for x in _csv("LLM_PROVIDERS")]
    if not order:
        order = [env("LLM_PROVIDER", "gemini").lower()]
        fb = env("LLM_FALLBACK_PROVIDER").lower()
        if fb:
            order.append(fb)
    order = ["custom" if x == "openai_compat" else x for x in order]
    g["LLM_PROVIDERS"] = [x for x in dict.fromkeys(order) if x in PROVIDERS]
    g["LLM_PROVIDER"] = g["LLM_PROVIDERS"][0] if g["LLM_PROVIDERS"] else "gemini"

    g["GEMINI_API_KEY"] = env("GEMINI_API_KEY")
    g["GEMINI_MODEL"] = env("GEMINI_MODEL", "gemini-flash-latest")
    g["GEMINI_FALLBACK_MODELS"] = _csv("GEMINI_FALLBACK_MODELS")
    g["GEMINI_TIMEOUT"] = _num("GEMINI_TIMEOUT", 600, int)
    g["GEMINI_DAILY_LIMIT"] = _num("GEMINI_DAILY_LIMIT", 0, int)
    g["ANTHROPIC_API_KEY"] = env("ANTHROPIC_API_KEY")
    g["ANTHROPIC_MODEL"] = env("ANTHROPIC_MODEL", "claude-sonnet-5-5")
    g["ANTHROPIC_VISION_MODEL"] = env("ANTHROPIC_VISION_MODEL", "claude-haiku-5-5")
    g["OPENAI_API_KEY"] = env("OPENAI_API_KEY")  # also used for ChatGPT chat, images and voice
    g["OPENAI_COMPAT_API_KEY"] = env("OPENAI_COMPAT_API_KEY")
    g["OPENAI_COMPAT_MODEL"] = env("OPENAI_COMPAT_MODEL")
    g["OPENAI_COMPAT_BASE_URL"] = env("OPENAI_COMPAT_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")

    # ---- voice
    g["VOICE_PROVIDER"] = env("VOICE_PROVIDER", "edge").lower()  # edge | elevenlabs | openai
    g["EDGE_VOICE"] = env("EDGE_VOICE", "en-US-AndrewNeural")
    g["ELEVENLABS_API_KEY"] = env("ELEVENLABS_API_KEY")
    g["ELEVENLABS_MODEL"] = env("ELEVENLABS_MODEL", "eleven_v4")
    g["ELEVENLABS_STABILITY"] = _num("ELEVENLABS_STABILITY", 0.5)
    g["ELEVENLABS_VOICE_ID"] = env("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
    g["OPENAI_TTS_MODEL"] = env("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
    g["OPENAI_TTS_VOICE"] = env("OPENAI_TTS_VOICE", "alloy")
    g["VOICE_FALLBACK"] = _flag("VOICE_FALLBACK", "1")
    g["MUSIC_SOURCE"] = env("MUSIC_SOURCE", "auto").lower()  # auto | library | generated
    g["MUSIC_VOLUME"] = _num("MUSIC_VOLUME", 0.15)
    g["VOICE_LUFS"] = _num("VOICE_LUFS", -15)

    # ---- footage
    g["PEXELS_API_KEY"] = env("PEXELS_API_KEY")
    g["PIXABAY_API_KEY"] = env("PIXABAY_API_KEY")
    g["TMDB_API_KEY"] = env("TMDB_API_KEY")
    g["DESCRIBE_TRAILER_SCENES"] = _flag("DESCRIBE_TRAILER_SCENES", "1")
    g["SHORT_FILL"] = _num("SHORT_FILL", 0.8)
    g["SHORT_PAN"] = _flag("SHORT_PAN", "1")
    g["PREFER_VERTICAL"] = _flag("PREFER_VERTICAL_TRAILERS", "1")
    g["SHORT_THUMBNAILS"] = _flag("SHORT_THUMBNAILS", "0")
    g["OPENAI_IMAGE_MODEL"] = env("OPENAI_IMAGE_MODEL", "gpt-image-1")

    # ---- misc
    g["YOUTUBE_DAILY_UPLOADS"] = _num("YOUTUBE_DAILY_UPLOADS", 6, int)
    g["WORKER_THREADS"] = _num("WORKER_THREADS", 1, int)
    g["USE_EMBEDDINGS"] = _flag("USE_EMBEDDINGS")
    g["FONT_PATH"] = env("FONT_PATH")
    g["ALLOW_SILENT_DRYRUN"] = _flag("ALLOW_SILENT_DRYRUN", "1")

    # ---- picture quality. Clips are cut at 1080p (fast); the final encode upsizes once, so 4K costs one slower step.
    g["OUTPUT_RES_SHORT"] = env("OUTPUT_RES_SHORT", "4k").lower()   # 1080p | 1440p | 4k
    g["OUTPUT_RES_LONG"] = env("OUTPUT_RES_LONG", "1440p").lower()
    g["HW_ENCODE"] = _flag("HW_ENCODE", "1")                         # use the graphics card's encoder when available

    # ---- hook (the first seconds) and API saving
    g["HOOK_ENABLED"] = _flag("HOOK_ENABLED", "1")
    g["HOOK_SECONDS"] = _num("HOOK_SECONDS", 4.5)
    g["HOOK_STYLE"] = env("HOOK_STYLE", "auto").lower()              # auto (follows the mood) | balanced | romance | action | shock | comedy | emotional
    g["BUDGET_MODE"] = _flag("BUDGET_MODE", "1")                     # fewer AI requests per video
    g["RANK_THUMBNAILS"] = _flag("RANK_THUMBNAILS", "0")             # extra AI call to rank posters (off = ranked in the idea call)

    # ---- publishing to Instagram and Facebook (Meta Graph API)
    g["META_ACCESS_TOKEN"] = env("META_ACCESS_TOKEN")
    g["FB_PAGE_ID"] = env("FB_PAGE_ID")
    g["IG_USER_ID"] = env("IG_USER_ID")
    g["META_GRAPH_VERSION"] = env("META_GRAPH_VERSION", "v25.0")

    # ---- upload defaults
    g["PUBLISH_YOUTUBE"] = _flag("PUBLISH_YOUTUBE", "1")
    g["PUBLISH_INSTAGRAM"] = _flag("PUBLISH_INSTAGRAM", "1")
    g["PUBLISH_FACEBOOK"] = _flag("PUBLISH_FACEBOOK", "1")
    g["YT_PRIVACY"] = env("YT_PRIVACY", "private").lower()
    g["OFFICIAL_CLIPS_SHORTS"] = _flag("OFFICIAL_CLIPS_SHORTS", "0")  # Shorts too: add 1 official clip per movie (more scenes, more AI requests)
    g["SHORT_SHOT_SECONDS"] = _num("SHORT_SHOT_SECONDS", 2.4)          # length of each cut in a Short (shorter = faster, more cuts)
    g["LONG_SHOT_SECONDS"] = _num("LONG_SHOT_SECONDS", 4.0)
    g["OFFICIAL_CLIPS"] = _flag("OFFICIAL_CLIPS", "1")  # one-movie long videos: add the studio's official clips to the trailer

    # ---- hook polish, research, source quality, hard time limits
    g["HOOK_SFX"] = _flag("HOOK_SFX", "1")                             # a short bass hit at the very start
    g["TREND_RESEARCH"] = _flag("TREND_RESEARCH", "1")                 # look at what is already popular on the topic
    g["TRAILER_MAX_HEIGHT"] = _num("TRAILER_MAX_HEIGHT", 2160, int)    # 1080 | 1440 | 2160: best trailer quality to download
    g["CLIP_RES"] = env("CLIP_RES", "1080p").lower()                   # 1080p (fast) | match (cut clips at the final size: sharper, slower)
    g["SHORT_MAX_SECONDS"] = _num("SHORT_MAX_SECONDS", 30, int)        # voice is sped up (max 1.2x) to finish within this
    g["SINGLE_MAX_SECONDS"] = _num("SINGLE_MAX_SECONDS", 20, int)
    g["LONG_MAX_SECONDS"] = _num("LONG_MAX_SECONDS", 180, int)
    g["EDGE_VOICE_FEMALE"] = env("EDGE_VOICE_FEMALE", "en-US-AriaNeural")             # used when the narrator is a female protagonist

    # ---- one-movie Shorts (about 20 s): hook + the film + outro
    g["SINGLE_TARGET_WORDS"] = _num("SINGLE_TARGET_WORDS", 44, int)
    g["SINGLE_MAX_WORDS"] = _num("SINGLE_MAX_WORDS", 50, int)
    g["SINGLE_SEGMENTS"] = env("SINGLE_SEGMENTS", "3")

    # ---- video lengths (about 2.5 spoken words per second; 500 words is about 3.3 minutes)
    st, sm = _num("SHORT_TARGET_WORDS", 62, int), _num("SHORT_MAX_WORDS", 70, int)
    lt, lm = _num("LONG_TARGET_WORDS", 360, int), _num("LONG_MAX_WORDS", 420, int)
    g["FORMATS"] = {
        "short": {"w": 1080, "h": 1920, "target_words": st, "max_words": sm, "segments": env("SHORT_SEGMENTS", "5"),
                  "caption_words": 4, "length_text": f"vertical YouTube Short, about {round(st / 2.5)} seconds (never longer than {round(sm / 2.5)} seconds)"},
        "long": {"w": 1920, "h": 1080, "target_words": lt, "max_words": lm, "segments": env("LONG_SEGMENTS", "12 to 16"),
                 "caption_words": 8, "length_text": f"horizontal long-form video, about {lt / 150:.1f} minutes (never longer than {lm / 150:.1f} minutes)"},
    }


RES = {"1080p": 1080, "1440p": 1440, "4k": 2160, "2160p": 2160}


def output_size(fmt):
    """(width, height) of the final video."""
    short_side = RES.get(globals()["OUTPUT_RES_SHORT" if fmt == "short" else "OUTPUT_RES_LONG"], 1080)
    long_side = round(short_side * 16 / 9 / 2) * 2
    return (short_side, long_side) if fmt == "short" else (long_side, short_side)


def provider_ready(name) -> bool:
    p = PROVIDERS.get(name)
    if not p:
        return False
    has_key = bool(env(p["key"]))
    if p["kind"] == "gemini":
        return has_key
    if p["kind"] == "anthropic":
        return has_key
    return has_key and bool(env(p["model"])) and bool(provider_base(name))


def reload():
    load_dotenv(ENV_FILE, override=True)
    _load()


load_dotenv(ENV_FILE)
_load()
