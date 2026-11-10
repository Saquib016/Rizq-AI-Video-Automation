"""Looks at what is already popular on the topic (titles, view counts, links) so the hook can use the angles that earn views.
It only READS titles and numbers; nothing is downloaded or copied, and the script is always original."""
import json
import time

from .. import config

CACHE = config.STORAGE / "trends.json"


def _load():
    try:
        return json.loads(CACHE.read_text())
    except Exception:
        return {}


def _fmt(n):
    n = int(n or 0)
    return f"{n / 1e6:.1f}M" if n >= 1e6 else f"{n / 1e3:.0f}K" if n >= 1e3 else str(n)


def viral_entries(topic: str):
    """[{title, views, duration, url}] for the most viewed videos and Shorts about the topic."""
    key = (topic or "").strip().lower()
    if not key:
        return []
    cache = _load()
    hit = cache.get(key)
    if hit and time.time() - hit["t"] < 12 * 3600 and "entries" in hit:
        return hit["entries"]
    entries = []
    try:
        import yt_dlp
        rows = {}
        opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "socket_timeout": 10}
        with yt_dlp.YoutubeDL(opts) as ydl:
            for q in (f"ytsearch8:{topic}", f"ytsearch6:{topic} shorts"):
                info = ydl.extract_info(q, download=False)
                for e in info.get("entries", []) or []:
                    if e.get("title") and e.get("view_count"):
                        url = e.get("url") or (f"https://www.youtube.com/watch?v={e['id']}" if e.get("id") else "")
                        rows[e["title"].strip()] = {"title": e["title"].strip(), "views": int(e["view_count"]), "duration": int(e.get("duration") or 0), "url": url}
        entries = sorted(rows.values(), key=lambda r: -r["views"])[:7]
    except Exception:
        entries = []
    cache[key] = {"t": time.time(), "entries": entries}
    try:
        CACHE.write_text(json.dumps(cache)[-200000:])
    except Exception:
        pass
    return entries


def as_text(entries) -> str:
    return "\n".join(f"- {e['title']} ({_fmt(e['views'])} views, {e['duration']}s)" for e in entries)


def viral_context(topic: str) -> str:
    return as_text(viral_entries(topic))
