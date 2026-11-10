import asyncio
import requests
from pathlib import Path

from .. import config, media

PAD = 0.25  # seconds of breathing room after each segment


def _count(text):
    from .. import db
    db.add_usage("elevenlabs_chars", len(text))


class QuotaError(RuntimeError):
    """ElevenLabs credits / character quota used up."""


def _is_quota(status, text):
    t = (text or "").lower()
    return status == 402 or "quota" in t or "credits" in t or "character limit" in t


EMOTION_TAGS = {"excited", "curious", "whispering", "serious", "sad", "nervous", "angry", "laughing", "sarcastic", "calm"}
MOOD_DEFAULT_TAG = {"horror": "whispering", "suspense": "curious", "thriller": "serious", "action": "excited",
                    "drama": "serious", "romance": "calm", "scifi": "curious", "comedy": "excited"}
API = "https://api.elevenlabs.io/v1"


def _tts_eleven(text, voice_id, out_mp3: Path):
    model = config.ELEVENLABS_MODEL
    expressive = model.startswith(("eleven_v3", "eleven_v4"))  # these read [audio tags] and only the stability setting
    settings = ({"stability": config.ELEVENLABS_STABILITY} if expressive else
                {"stability": config.ELEVENLABS_STABILITY, "similarity_boost": 0.8, "style": 0.2})
    headers = {"xi-api-key": config.ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    r = requests.post(f"{API}/text-to-speech/{voice_id}", params={"output_format": "mp3_44100_128"}, headers=headers,
                      json={"text": text, "model_id": model, "voice_settings": settings}, timeout=180)
    if r.status_code == 200:
        out_mp3.write_bytes(r.content)
        _count(text)
        return
    if _is_quota(r.status_code, r.text):
        raise QuotaError(f"ElevenLabs credits used up: {r.text[:200]}")
    first = f"ElevenLabs error {r.status_code}: {r.text[:300]}"
    if expressive and r.status_code in (400, 404, 405, 422):
        # v4 may be served through the Text to Dialogue endpoint instead; try that before giving up
        r2 = requests.post(f"{API}/text-to-dialogue", params={"output_format": "mp3_44100_128"}, headers=headers,
                           json={"inputs": [{"text": text, "voice_id": voice_id}], "model_id": model,
                                 "settings": {"stability": config.ELEVENLABS_STABILITY}}, timeout=180)
        if r2.status_code == 200:
            out_mp3.write_bytes(r2.content)
            _count(text)
            return
        if _is_quota(r2.status_code, r2.text):
            raise QuotaError(f"ElevenLabs credits used up: {r2.text[:200]}")
        first += f" | dialogue endpoint {r2.status_code}: {r2.text[:300]}"
    raise RuntimeError(first + f" (model '{model}', voice '{voice_id}')")


def _tagged(seg, mood):
    """Eleven v3/v4 take emotion as an inline tag, e.g. '[excited] Text'. Captions keep the plain narration."""
    if not config.ELEVENLABS_MODEL.startswith(("eleven_v3", "eleven_v4")):
        return seg.get("speech") or seg["narration"]
    tag = str(seg.get("emotion") or "").lower().strip(" []")
    if tag not in EMOTION_TAGS:
        tag = MOOD_DEFAULT_TAG.get(mood or "", "")
    spoken = seg.get("speech") or seg["narration"]
    return f"[{tag}] {spoken}" if tag else spoken


def _tts_openai(text, voice, out_mp3: Path, emotion=""):
    """ChatGPT voices (OpenAI text-to-speech). gpt-4o-mini-tts also accepts a delivery instruction."""
    if not config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is missing (needed for the OpenAI voice).")
    body = {"model": config.OPENAI_TTS_MODEL, "voice": voice or config.OPENAI_TTS_VOICE, "input": text,
            "response_format": "mp3"}
    if "gpt-4o" in config.OPENAI_TTS_MODEL and emotion:
        body["instructions"] = f"Speak in a {emotion} tone, like an engaging movie narrator."
    r = requests.post("https://api.openai.com/v1/audio/speech",
                      headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"}, json=body, timeout=180)
    if r.status_code != 200:
        if r.status_code == 429 or "quota" in r.text.lower():
            raise QuotaError(f"OpenAI voice quota/limit: {r.text[:200]}")
        raise RuntimeError(f"OpenAI voice error {r.status_code}: {r.text[:250]}")
    out_mp3.write_bytes(r.content)
    from .. import db
    db.add_usage("openai_tts_chars", len(text))


def _tts_edge(text, voice, out_mp3: Path):
    try:
        import edge_tts
    except ImportError:
        raise RuntimeError("edge-tts is not installed. Run: pip install edge-tts")

    async def go():
        await edge_tts.Communicate(text, voice).save(str(out_mp3))

    try:
        asyncio.run(go())
    except Exception as e:
        if "403" in str(e) or "401" in str(e):
            raise RuntimeError(
                "Microsoft rejected the free voice connection (403). Fix: run  python -m pip install -U edge-tts  "
                "(version 7.3.1 or newer; older versions stopped working in Oct 2026), then restart. "
                "If it still fails: turn off any VPN, make sure your PC clock is correct, or wait and retry.")
        raise RuntimeError(f"edge-tts failed (needs internet; check the voice name '{voice}'): {str(e)[:200]}")


def synthesize(segments, voice_id, work: Path, progress=lambda p: None, mood=None, provider=None, gender=None):
    """Creates one WAV per segment. If ElevenLabs runs out of credits, the WHOLE video is redone with the free
    Edge voice (never a mix of two voices in one video) and info['fallback_reason'] is set."""
    provider = (provider or config.VOICE_PROVIDER).lower()
    try:
        return _synth(segments, voice_id, work, progress, mood, provider, gender)
    except QuotaError as e:
        if provider in ("elevenlabs", "openai") and config.VOICE_FALLBACK:
            info = _synth(segments, None, work, progress, mood, "edge", gender)
            info["fallback_reason"] = str(e)[:200]
            return info
        raise


def _synth(segments, voice_id, work: Path, progress, mood, provider, gender=None):
    """Creates one WAV per segment (with trailing pad). Sets seg['audio'] and seg['duration']."""
    silent = provider == "elevenlabs" and not config.ELEVENLABS_API_KEY
    if silent and not config.ALLOW_SILENT_DRYRUN:
        raise RuntimeError("ELEVENLABS_API_KEY is missing. Add it to your .env file.")
    if provider == "edge":
        # a channel/voice field is only used if it looks like an edge voice name (e.g. en-US-AriaNeural)
        voice = voice_id if voice_id and voice_id.endswith("Neural") else (config.EDGE_VOICE_FEMALE if gender == "female" else config.EDGE_VOICE)
    elif provider == "openai":
        voice = voice_id if voice_id and "-" not in voice_id and len(voice_id) < 20 else config.OPENAI_TTS_VOICE
    else:
        voice = voice_id or config.ELEVENLABS_VOICE_ID

    audio_dir = work / "audio"
    audio_dir.mkdir(exist_ok=True)
    for i, seg in enumerate(segments):
        wav = audio_dir / f"seg{i:03d}.wav"
        if silent:
            secs = max(1.5, len(seg["narration"].split()) / 2.6)
            media.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                       "-t", f"{secs + PAD:.2f}", str(wav)])
        else:
            mp3 = audio_dir / f"seg{i:03d}.mp3"
            if provider == "edge":
                _tts_edge(seg.get("speech") or seg["narration"], voice, mp3)
            elif provider == "openai":
                _tts_openai(seg.get("speech") or seg["narration"], voice, mp3, str(seg.get("emotion") or ""))
            else:
                _tts_eleven(_tagged(seg, mood), voice, mp3)
            media.run(["ffmpeg", "-y", "-i", str(mp3), "-af", f"apad=pad_dur={PAD}",
                       "-ar", "44100", "-ac", "2", str(wav)])
        seg["audio"] = str(wav)
        seg["duration"] = media.duration(wav)
        progress((i + 1) / len(segments))
    return {"silent_dryrun": silent}


def fit_to_limit(segments, cap_seconds, work: Path):
    """If the finished voice is longer than the limit, speed it up a little (at most 1.2x) so the video ends in time."""
    total = sum(s["duration"] for s in segments)
    info = {"total": round(total, 1), "factor": 1.0}
    if total <= cap_seconds:
        return info
    factor = min(1.2, total / cap_seconds)
    fast = work / "audio_fast"
    fast.mkdir(exist_ok=True)
    for i, seg in enumerate(segments):
        out = fast / f"seg{i:03d}.wav"
        media.run(["ffmpeg", "-y", "-i", seg["audio"], "-filter:a", f"atempo={factor:.4f}", "-ar", "44100", "-ac", "2", str(out)])
        seg["audio"], seg["duration"] = str(out), media.duration(out)
    info.update(factor=round(factor, 2), total=round(sum(s["duration"] for s in segments), 1))
    return info
