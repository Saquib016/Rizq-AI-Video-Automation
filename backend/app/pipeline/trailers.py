"""Find the official trailer for each movie, download it once, and cut it into scenes.

NOTE: trailers are copyrighted by the studios. This module only fetches them so the editor can use
short clips under your own commentary. The API layer requires the user to acknowledge this.
"""
import json
import re
import subprocess
from pathlib import Path

import requests

from .. import config, llm, media, movies as movie_utils

BAD_WORDS = ("reaction", "review", "explained", "breakdown", "fan made", "fanmade", "fan-made",
             "recap", "ending", "scene", "clip", "parody", "react", "analysis", "theory")


def slug(title, year=None):
    s = re.sub(r"[^a-z0-9]+", "-", f"{title}-{year or ''}".lower()).strip("-")
    return s[:80] or "movie"


# ---------- finding the trailer ----------
def _tmdb_trailer(title, year):
    """Returns (youtube_url, canonical_title, year) or None. Optional: needs TMDB_API_KEY (free)."""
    if not config.TMDB_API_KEY:
        return None
    try:
        params = {"api_key": config.TMDB_API_KEY, "query": title}
        if year:
            params["year"] = year
        r = requests.get("https://api.themoviedb.org/3/search/movie", params=params, timeout=20)
        res = r.json().get("results", []) if r.status_code == 200 else []
        if not res:
            return None
        m = res[0]
        v = requests.get(f"https://api.themoviedb.org/3/movie/{m['id']}/videos",
                         params={"api_key": config.TMDB_API_KEY}, timeout=20).json().get("results", [])
        yt = [x for x in v if x.get("site") == "YouTube" and x.get("type") == "Trailer"]
        yt.sort(key=lambda x: (not x.get("official"), x.get("size", 0) * -1))
        if not yt:
            return None
        return (f"https://www.youtube.com/watch?v={yt[0]['key']}", m.get("title", title),
                (m.get("release_date") or "")[:4])
    except Exception:
        return None


def _search_trailer(title, year):
    import yt_dlp
    q = f"{title} {year or ''} official trailer".strip()
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": True}) as ydl:
        info = ydl.extract_info(f"ytsearch8:{q}", download=False)
    best, best_score = None, -99
    for e in info.get("entries", []) or []:
        t = (e.get("title") or "").lower()
        dur = e.get("duration") or 0
        if "trailer" not in t or any(b in t for b in BAD_WORDS):
            continue
        if dur and not (40 <= dur <= 300):
            continue
        score = 3 * ("official" in t) + 2 * (title.lower() in t) + 1 * (str(year) in t if year else 0)
        if score > best_score:
            best, best_score = e, score
    if not best:
        return None
    url = best.get("url") or f"https://www.youtube.com/watch?v={best.get('id')}"
    return url, best.get("title", ""), best.get("channel") or best.get("uploader") or ""


def pick_vertical(entries, title):
    """From search results, choose an official-looking vertical clip (a YouTube Short) for this movie, or None."""
    nt = movie_utils.norm(title)
    best, best_score = None, 0
    for e in entries or []:
        t = (e.get("title") or "").lower()
        url = e.get("url") or ""
        dur = e.get("duration") or 0
        is_short = "/shorts/" in url or "#shorts" in t
        if not is_short or "official" not in t or not ("trailer" in t or "teaser" in t):
            continue
        if nt not in movie_utils.norm(t) or any(b in t for b in BAD_WORDS):
            continue
        if dur and not (8 <= dur <= 90):
            continue
        score = 2 + 2 * ("/shorts/" in url) + 1 * ("#shorts" in t)
        if score > best_score:
            best, best_score = e, score
    return best


def _search_vertical(title, year):
    import yt_dlp
    q = f"{title} {year or ''} official trailer shorts".strip()
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": True}) as ydl:
        info = ydl.extract_info(f"ytsearch12:{q}", download=False)
    e = pick_vertical(info.get("entries"), title)
    if not e:
        return None
    return (e.get("url") or f"https://www.youtube.com/shorts/{e.get('id')}", e.get("title", ""),
            e.get("channel") or e.get("uploader") or "")


def _try_vertical(title, year, d: Path, progress):
    """Returns meta for a vertical clip, or None (then the normal landscape trailer is used)."""
    vmeta, marker = d / "meta_vertical.json", d / "no_vertical"
    if vmeta.exists():
        m = json.loads(vmeta.read_text())
        if Path(m["path"]).exists():
            return m
    if marker.exists():
        return None
    try:
        found = _search_vertical(title, year)
        if not found:
            marker.write_text("1")
            return None
        url = found[0]
        path, info = _download(url, d / "vertical", vertical=True)
        w, h = _dims(path)
        if h < w * 1.2 or w < 1000:  # not vertical, or below 1080p quality: use the normal 16:9 trailer instead
            import shutil as _sh
            _sh.rmtree(d / "vertical", ignore_errors=True)
            marker.write_text("1")
            return None
        scenes = detect_scenes(path, min_len=1.0)
        if not scenes:
            return None
        _describe(path, scenes, d / "frames_v")
        meta = {"title": title, "year": year, "path": str(path), "url": url, "vertical": True,
                "video_title": info.get("title", found[1]), "channel": info.get("channel") or info.get("uploader") or found[2],
                "scenes": scenes, "duration": media.duration(path)}
        vmeta.write_text(json.dumps(meta, indent=1))
        return meta
    except Exception:
        return None


def _dims(path):
    p = media.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                   "stream=width,height", "-of", "json", path])
    st = json.loads(p.stdout)["streams"][0]
    return st["width"], st["height"]


def _download(url, dest: Path, vertical=False):
    import yt_dlp
    dest.mkdir(parents=True, exist_ok=True)
    fmt = ("bv*[width<=1080][vcodec!*=av01]+ba/bv*[width<=1080]+ba/b[width<=1080]/b" if vertical else
           f"bv*[height<={config.TRAILER_MAX_HEIGHT}][vcodec!*=av01]+ba/bv*[height<={config.TRAILER_MAX_HEIGHT}]+ba/b[height<={config.TRAILER_MAX_HEIGHT}]/b")
    opts = {"outtmpl": str(dest / "trailer.%(ext)s"), "format": fmt,
            "merge_output_format": "mp4", "noplaylist": True, "quiet": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    f = next(iter(sorted(dest.glob("trailer.mp4"))), None) or next(
        (p for p in dest.glob("trailer.*") if p.suffix not in (".json", ".part")), None)
    if not f:
        raise RuntimeError("download finished but no file found")
    return f, info


# ---------- cutting into scenes ----------
def detect_scenes(video: Path, threshold=0.30, min_len=1.2, max_len=4.5):
    total = media.duration(video)
    p = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(video), "-an", "-vf",
         f"scale=320:-2,select='gt(scene,{threshold})',showinfo", "-f", "null", "-"],
        capture_output=True, text=True)
    cuts = sorted({float(x) for x in re.findall(r"pts_time:([0-9.]+)", p.stderr)})
    bounds = [0.0] + [c for c in cuts if 0 < c < total] + [total]
    scenes = []
    for a, b in zip(bounds, bounds[1:]):
        if b - a < min_len:
            continue
        t = a
        while t < b - min_len:  # split long scenes into shorter windows
            e = min(b, t + max_len)
            if b - e < min_len:
                e = b
            scenes.append({"start": round(t, 2), "end": round(e, 2)})
            t = e
    # skip studio logos at the start and title/rating cards at the end
    lo, hi = min(6.0, total * 0.06), total * 0.88
    kept = [s for s in scenes if s["start"] >= lo and s["end"] <= hi]
    return kept or scenes


HOOK_TAGS = ["kiss", "romance", "intimate", "action", "fight", "explosion", "chase", "shock", "scare", "reveal",
             "emotional", "funny", "dialogue", "landscape", "crowd", "title"]


def _describe(video: Path, scenes, work: Path):
    """One AI request describes up to 16 scenes at once and also returns, for each:
    hook (0-10: how scroll-stopping as the opening shot), tags, and explicit (nudity / explicit sex -> scene is dropped)."""
    if not (config.DESCRIBE_TRAILER_SCENES and llm.available()):
        return
    work.mkdir(parents=True, exist_ok=True)
    idxs = list(range(len(scenes)))
    cap = 24 if config.BUDGET_MODE else 60
    if len(idxs) > cap:  # spread the described scenes evenly over the trailer
        step = len(idxs) / cap
        idxs = [int(i * step) for i in range(cap)]
    for i in idxs:
        f = work / f"s{i:03d}.jpg"
        media.extract_frame(str(video), str(f), (scenes[i]["start"] + scenes[i]["end"]) / 2, width=384)
        scenes[i]["frame"] = str(f)
    per = 16 if config.BUDGET_MODE else 10
    for b in range(0, len(idxs), per):
        batch = [scenes[i] for i in idxs[b:b + per]]
        try:
            out = llm.ask_json(
                "You analyse movie trailer frames for a video editor who needs scroll-stopping opening shots.",
                f"There are {len(batch)} images, in order. For EACH image return an object:\n"
                '{"d": "one short factual sentence (who/what is visible, setting, action, mood; never name actors)",'
                ' "hook": 0-10 integer (how well this works as the first second of a YouTube Short: close-up emotion, '
                "chemistry or a kiss, a fight, an explosion, a shock, a jump scare or a big reveal score high; "
                "empty establishing shots, logos, title cards, text and crowds walking score low),"
                f' "tags": a list chosen only from {HOOK_TAGS},'
                ' "explicit": true ONLY if there is nudity or an explicit sexual act, or any sexualised depiction of '
                "someone who looks under 18; otherwise false}\n"
                "Return a JSON array with exactly one object per image, in the same order.",
                images=[s["frame"] for s in batch], model=config.ANTHROPIC_VISION_MODEL, max_tokens=2500)
            for sc, d in zip(batch, out):
                if isinstance(d, dict):
                    sc["description"] = str(d.get("d", ""))
                    try:
                        sc["hook"] = max(0.0, min(10.0, float(d.get("hook"))))
                    except (TypeError, ValueError):
                        pass
                    sc["tags"] = [t for t in d.get("tags", []) if isinstance(t, str)][:4]
                    sc["explicit"] = bool(d.get("explicit"))
                else:
                    sc["description"] = str(d)
        except Exception:
            pass  # without descriptions the scenes still work (order + a cheap heuristic for the hook)
    for sc in scenes:
        sc.pop("frame", None)
    scenes[:] = [sc for sc in scenes if not sc.get("explicit")]  # never use nudity / explicit scenes


CLIP_BAD = ("reaction", "review", "explained", "breakdown", "fan made", "fanmade", "fan-made", "recap", "ending", "parody",
            "analysis", "theory", "compilation", "all scenes", "top 10", "ranked", "deleted")


def official_clips(title, year, d: Path, max_clips=2):
    """Official clips, featurettes and teasers from the studio or a licensed channel (such as Movieclips) for the same film."""
    import yt_dlp
    d.mkdir(parents=True, exist_ok=True)
    cache = d / "clips_meta.json"
    if cache.exists():
        try:
            metas = json.loads(cache.read_text())
            if metas and all(Path(m["path"]).exists() for m in metas):
                return metas
        except Exception:
            pass
    nt = movie_utils.norm(title)
    found = {}
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": True}) as ydl:
        for q in (f"{title} {year or ''} official clip", f"{title} {year or ''} movie clip", f"{title} {year or ''} official tv spot teaser"):
            info = ydl.extract_info(f"ytsearch8:{q.strip()}", download=False)
            for e in info.get("entries", []) or []:
                t, ch, dur = (e.get("title") or "").lower(), (e.get("channel") or e.get("uploader") or "").lower(), e.get("duration") or 0
                licensed = "movieclips" in ch
                if nt not in movie_utils.norm(t) or any(b in t for b in CLIP_BAD) or not (20 <= dur <= 420):
                    continue
                if not (("official" in t) or licensed) or not (licensed or any(w in t for w in ("clip", "scene", "featurette", "teaser", "tv spot"))):
                    continue
                url = e.get("url") or f"https://www.youtube.com/watch?v={e.get('id')}"
                found[url] = (2 * licensed + ("official" in t), e.get("title", ""), e.get("channel") or e.get("uploader") or "")
    metas = []
    for url, (_, vtitle, channel) in sorted(found.items(), key=lambda kv: -kv[1][0])[:max_clips]:
        try:
            folder = d / "clips" / f"c{len(metas)}"
            path, info = _download(url, folder)
            scenes = detect_scenes(path, min_len=1.2)
            if not scenes:
                continue
            _describe(path, scenes, folder / "frames")
            metas.append({"path": str(path), "url": url, "video_title": info.get("title", vtitle), "channel": info.get("channel") or channel,
                          "scenes": scenes, "duration": media.duration(path)})
        except Exception:
            continue
    if metas:
        cache.write_text(json.dumps(metas, indent=1))
    return metas


def merged(meta, extras):
    """The trailer plus the official clips as one pool of scenes (each scene remembers which file it is in)."""
    out = dict(meta)
    scenes = [dict(s) for s in meta["scenes"]]
    for e in extras:
        scenes += [dict(s, path=e["path"], src_duration=e["duration"]) for s in e["scenes"]]
    out["scenes"] = scenes
    out["extra_clips"] = [{"title": e["video_title"], "url": e["url"], "channel": e["channel"]} for e in extras]
    return out


def prepare(title, year=None, progress=lambda p: None, prefer_vertical=False):
    """Download (or reuse the cached) trailer and return its scenes. Raises if nothing can be found.
    prefer_vertical: for Shorts, try an official vertical clip first and fall back to the landscape trailer."""
    key = slug(title, year)
    d = config.TRAILERS / key
    d.mkdir(parents=True, exist_ok=True)
    if prefer_vertical:
        v = _try_vertical(title, year, d, progress)
        if v:
            progress(1.0)
            return v
    meta_file = d / "meta.json"
    if meta_file.exists():
        meta = json.loads(meta_file.read_text())
        if Path(meta["path"]).exists():
            return meta

    found = _tmdb_trailer(title, year)
    if found:
        url, vtitle, channel = found[0], f"{found[1]} trailer", "TMDB"
    else:
        s = _search_trailer(title, year)
        if not s:
            raise RuntimeError(f"No official trailer found for '{title}'.")
        url, vtitle, channel = s
    progress(0.2)
    path, info = _download(url, d)
    progress(0.6)
    scenes = detect_scenes(path)
    if not scenes:
        raise RuntimeError(f"Could not cut scenes from the '{title}' trailer.")
    _describe(path, scenes, d / "frames")
    meta = {"title": title, "year": year, "path": str(path), "url": url, "video_title": info.get("title", vtitle),
            "channel": info.get("channel") or info.get("uploader") or channel, "scenes": scenes,
            "duration": media.duration(path)}
    meta_file.write_text(json.dumps(meta, indent=1))
    progress(1.0)
    return meta
