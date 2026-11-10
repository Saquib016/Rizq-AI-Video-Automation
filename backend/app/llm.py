"""Talks to AI text providers: Gemini, Claude, ChatGPT (OpenAI), Grok (xAI), Groq, OpenRouter, DeepSeek, Mistral,
or any OpenAI-style API. Providers are tried in the order of LLM_PROVIDERS until one answers."""
import base64
import json
import re
import time
from pathlib import Path

import requests

from . import config

_cooldown = {}  # provider -> time until which it is skipped (after a quota error), so we do not keep hammering it


def available() -> bool:
    return any(config.provider_ready(p) for p in config.LLM_PROVIDERS)


def label() -> str:
    for p in config.LLM_PROVIDERS:
        if config.provider_ready(p):
            return config.PROVIDERS[p]["label"].split(" (")[0]
    return "AI"


def _parse_json(text: str):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"(\{.*\}|\[.*\])", text, flags=re.S)
        if not m:
            raise
        return json.loads(m.group(1))


def _mime(img):
    return "image/png" if str(img).lower().endswith(".png") else "image/jpeg"


def _b64(img):
    return base64.standard_b64encode(Path(img).read_bytes()).decode()


# ---------------------------------------------------------------- Claude
def _anthropic(system, user, images, model, max_tokens):
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is missing.")
    import anthropic
    content = [{"type": "image", "source": {"type": "base64", "media_type": _mime(i), "data": _b64(i)}} for i in images or []]
    content.append({"type": "text", "text": user})
    msg = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY).messages.create(
        model=model or config.ANTHROPIC_MODEL, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": content}])
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


# ---------------------------------------------------------------- Gemini
def _daily_exhausted(text: str) -> bool:
    t = text or ""
    return "PerDay" in t or "per day" in t.lower() or '"quotaValue": "0"' in t


def _retry_delay(text: str):
    m = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', text or "")
    return float(m.group(1)) if m else None


def _call_gemini(model, body):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    r = None
    for attempt in range(5):
        try:
            r = requests.post(url, headers={"x-goog-api-key": config.GEMINI_API_KEY}, json=body,
                              timeout=(20, config.GEMINI_TIMEOUT))
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            r = None
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code == 429:
            if _daily_exhausted(r.text):
                return r
            time.sleep(min(_retry_delay(r.text) or 20 * (attempt + 1), 90))
            continue
        if r.status_code in (500, 502, 503, 504):
            time.sleep(15 * (attempt + 1))
            continue
        return r
    return r


def _gemini(system, user, images, max_tokens):
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is missing. Get a free key at aistudio.google.com.")
    parts = [{"text": user}] + [{"inline_data": {"mime_type": _mime(i), "data": _b64(i)}} for i in images or []]
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": max_tokens}}
    models = [config.GEMINI_MODEL] + [m for m in config.GEMINI_FALLBACK_MODELS if m != config.GEMINI_MODEL]
    notes = []
    for model in models:
        r = _call_gemini(model, body)
        if r is None:
            notes.append(f"{model}: no connection")
            continue
        if r.status_code == 200:
            from . import db
            db.add_usage("gemini_requests", 1)
            cands = r.json().get("candidates") or []
            if not cands:
                raise RuntimeError("Gemini returned no answer (the request may have been blocked).")
            return "".join(p.get("text", "") for p in cands[0].get("content", {}).get("parts", []))
        notes.append(f"{model}: error {r.status_code} {'(daily quota used up)' if r.status_code == 429 and _daily_exhausted(r.text) else r.text[:160]}")
        if r.status_code in (400, 401, 403):
            break
    raise RuntimeError("Gemini could not answer. " + " | ".join(notes))


# ---------------------------------------------------------------- OpenAI-style APIs (ChatGPT, Grok, Groq, ...)
def _compat(name, system, user, images, max_tokens):
    p = config.PROVIDERS[name]
    key, model, base = config.env(p["key"]), config.env(p["model"]), config.provider_base(name)
    if not (key and model):
        raise RuntimeError(f"{p['label']}: API key or model is not set.")
    content = [{"type": "text", "text": user}] + [
        {"type": "image_url", "image_url": {"url": f"data:{_mime(i)};base64,{_b64(i)}"}} for i in images or []]
    body = {"model": model, "temperature": 0.7, "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": content if images else user}],
            "response_format": {"type": "json_object"}}
    url, headers = f"{base}/chat/completions", {"Authorization": f"Bearer {key}"}
    r = None
    for attempt in range(6):
        try:
            r = requests.post(url, headers=headers, json=body, timeout=(20, config.GEMINI_TIMEOUT))
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            r = None
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code == 400:
            t = r.text
            # newer models reject some classic parameters: adapt and retry
            if "max_completion_tokens" in t and "max_tokens" in body:
                body["max_completion_tokens"] = body.pop("max_tokens")
                continue
            if "temperature" in t and "temperature" in body:
                body.pop("temperature")
                continue
            if "response_format" in t and "response_format" in body:
                body.pop("response_format")
                continue
            break
        if r.status_code == 429:
            try:
                wait = float(r.headers.get("retry-after", 0))
            except ValueError:
                wait = 0
            if wait > 120:
                break
            time.sleep(min(wait or 15 * (attempt + 1), 60))
            continue
        if r.status_code >= 500:
            time.sleep(10 * (attempt + 1))
            continue
        break
    if r is None:
        raise RuntimeError(f"{p['label']}: could not connect ({base}).")
    if r.status_code != 200:
        raise RuntimeError(f"{p['label']} error {r.status_code} (model '{model}'): {r.text[:250]}")
    from . import db
    db.add_usage(f"{name}_requests", 1)
    return r.json()["choices"][0]["message"]["content"] or ""


def _run(name, system, user, images, model, max_tokens):
    kind = config.PROVIDERS[name]["kind"]
    if kind == "anthropic":
        return _anthropic(system, user, images, model, max_tokens)
    if kind == "gemini":
        return _gemini(system, user, images, max_tokens)
    return _compat(name, system, user, images, max_tokens)


def ask_json(system: str, user: str, images=None, model=None, max_tokens=8000):
    """Ask the first working provider for JSON."""
    system = system + "\n\nReturn ONLY valid JSON. No markdown fences, no commentary."
    ready = [p for p in config.LLM_PROVIDERS if config.provider_ready(p)]
    if not ready:
        raise RuntimeError("No AI provider is set up. Open Settings and add at least one key (Gemini is free).")
    now = time.time()
    active = [p for p in ready if _cooldown.get(p, 0) < now] or ready  # skip ones that just ran out of quota
    errors = []
    for prov in active:
        try:
            return _parse_json(_run(prov, system, user, images, model, max_tokens))
        except Exception as e:
            msg = str(e)
            errors.append(f"{config.PROVIDERS[prov]['label']}: {msg[:300]}")
            if "429" in msg or "quota" in msg.lower():
                _cooldown[prov] = time.time() + 1800
    raise RuntimeError(" || ".join(errors))


# ---------------------------------------------------------------- helpers for the Settings page
def ping(name):
    """Tiny test request. Returns {ok, ms, error}."""
    t0 = time.time()
    try:
        _cooldown.pop(name, None)
        out = _parse_json(_run(name, "Reply with JSON only.", 'Return exactly {"ok": true}', None, None, 60))
        return {"ok": bool(out), "ms": int((time.time() - t0) * 1000)}
    except Exception as e:
        return {"ok": False, "ms": int((time.time() - t0) * 1000), "error": str(e)[:400]}


def list_models(name):
    """Model names the key can use (so you can pick a valid one)."""
    p = config.PROVIDERS[name]
    key = config.env(p["key"])
    if not key:
        raise RuntimeError("Add the API key first.")
    if p["kind"] == "gemini":
        r = requests.get("https://generativelanguage.googleapis.com/v1beta/models", params={"pageSize": 200},
                         headers={"x-goog-api-key": key}, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"Error {r.status_code}: {r.text[:200]}")
        return sorted(m["name"].split("/", 1)[1] for m in r.json().get("models", [])
                      if "generateContent" in m.get("supportedGenerationMethods", []))
    if p["kind"] == "anthropic":
        r = requests.get("https://api.anthropic.com/v1/models", params={"limit": 100},
                         headers={"x-api-key": key, "anthropic-version": "2023-06-01"}, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"Error {r.status_code}: {r.text[:200]}")
        return sorted(m["id"] for m in r.json().get("data", []))
    r = requests.get(f"{config.provider_base(name)}/models", headers={"Authorization": f"Bearer {key}"}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Error {r.status_code}: {r.text[:200]}")
    return sorted(m["id"] for m in r.json().get("data", []) if m.get("id"))
