"""Scene matching: pick the best visual for each script segment.

Order of preference:
  1. Footage you uploaded to assets/library (and scenes from a source video you own)
  2. Pexels stock footage (free licence)
  3. A plain colour card (so the render never fails)
"""
import json
import re
from pathlib import Path

import requests

from .. import config

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
STOP = set("a an the of in on at to and or with for from by is are was were his her their its this that it as into over under".split())


def _tokens(text):
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in STOP and len(w) > 2}


def scan_library():
    """Every file in assets/library. Optional sidecar `<name>.json`: {"description": "...", "license": "..."}"""
    out = []
    for p in sorted(config.LIBRARY.iterdir()):
        ext = p.suffix.lower()
        if ext not in VIDEO_EXT | IMAGE_EXT:
            continue
        meta = {}
        side = p.with_suffix(".json")
        if side.exists():
            try:
                meta = json.loads(side.read_text(encoding="utf-8"))
            except Exception:
                pass
        out.append({
            "path": str(p),
            "kind": "video" if ext in VIDEO_EXT else "image",
            "description": meta.get("description") or p.stem.replace("_", " ").replace("-", " "),
            "source": "library",
            "license": meta.get("license", "user_library"),
        })
    return out


class Matcher:
    def __init__(self, assets):
        self.assets = assets
        self.use = {}
        self._model = None
        self._emb = None
        if config.USE_EMBEDDINGS and assets:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer("all-MiniLM-L6-v2")
                self._emb = self._model.encode([a["description"] or "" for a in assets], normalize_embeddings=True)
            except Exception:
                self._model = None

    def best(self, query, min_score=0.12):
        if not self.assets:
            return None
        if self._model is not None:
            q = self._model.encode([query], normalize_embeddings=True)[0]
            scores = (self._emb @ q).tolist()
        else:
            qt = _tokens(query)
            scores = []
            for a in self.assets:
                at = _tokens(a["description"])
                scores.append(len(qt & at) / (len(qt | at) or 1))
        # penalise reuse so the video doesn't repeat one clip
        ranked = sorted(range(len(self.assets)), key=lambda i: scores[i] - 0.08 * self.use.get(i, 0), reverse=True)
        i = ranked[0]
        if scores[i] < min_score:
            return None
        self.use[i] = self.use.get(i, 0) + 1
        return {**self.assets[i], "score": round(float(scores[i]), 3)}


def pexels_clip(query, orientation, dest: Path, idx: int):
    if not config.PEXELS_API_KEY:
        return None
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": config.PEXELS_API_KEY},
            params={"query": query, "orientation": orientation, "per_page": 6, "size": "medium"},
            timeout=30,
        )
        if r.status_code != 200:
            return None
        vids = r.json().get("videos", [])
        if not vids:
            return None
        v = vids[idx % min(len(vids), 3)]
        files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4"]
        files.sort(key=lambda f: abs((f.get("width") or 0) - 1080))
        if not files:
            return None
        out = dest / f"pexels_{v['id']}.mp4"
        if not out.exists():
            data = requests.get(files[0]["link"], timeout=120)
            out.write_bytes(data.content)
        return {"path": str(out), "kind": "video", "description": query, "source": "pexels",
                "license": "pexels", "credit": v.get("user", {}).get("name", "")}
    except Exception:
        return None


def pixabay_clip(query, dest: Path, idx: int, orientation=None):
    if not config.PIXABAY_API_KEY:
        return None
    try:
        r = requests.get(
            "https://pixabay.com/api/videos/",
            params={"key": config.PIXABAY_API_KEY, "q": " ".join(query.split()[:6]), "per_page": 6, "safesearch": "true"},
            timeout=30,
        )
        if r.status_code != 200:
            return None
        hits = r.json().get("hits", [])
        if orientation == "landscape":  # long videos are always 16:9: skip vertical stock clips
            hits = [h for h in hits if (h["videos"].get("medium") or h["videos"].get("large") or {}).get("width", 1) >= (h["videos"].get("medium") or h["videos"].get("large") or {}).get("height", 0)]
        if not hits:
            return None
        h = hits[idx % min(len(hits), 3)]
        v = h["videos"].get("medium") or h["videos"].get("large") or h["videos"].get("small")
        if not v or not v.get("url"):
            return None
        out = dest / f"pixabay_{h['id']}.mp4"
        if not out.exists():
            out.write_bytes(requests.get(v["url"], timeout=120).content)
        return {"path": str(out), "kind": "video", "description": query, "source": "pixabay",
                "license": "pixabay", "credit": h.get("user", "")}
    except Exception:
        return None


class TrailerPool:
    """Scenes from one movie's trailer. Each scene is used once before any is reused."""

    def __init__(self, meta):
        self.meta = meta
        self.scenes = meta["scenes"]
        self.unused = list(range(len(self.scenes)))

    def shot(self, i, each):
        sc = self.scenes[i]
        total = sc.get("src_duration", self.meta.get("duration", 9999))
        return {"path": sc.get("path", self.meta["path"]), "start": round(min(sc["start"] + 0.05, max(0, total - each - 0.1)), 2), "dur": round(each, 3)}

    def hook_candidates(self, style):
        n = len(self.scenes)
        return [(hook_score(self.scenes[i], i, n, style), i) for i in self.unused]

    def take_hook(self, seconds, fmt, style, picks=None):
        """Strongest scenes first, cut fast: the first shot is the single best moment of the trailer."""
        per = 1.5 if fmt == "short" else 2.4
        n = max(1, round(seconds / per))
        cands = picks if picks is not None else sorted(self.hook_candidates(style), reverse=True)[:n]
        chosen = [i for _, i in cands[:n]]
        for i in chosen:
            if i in self.unused:
                self.unused.remove(i)
        each = seconds / max(1, len(chosen))
        return [self.shot(i, each) for i in chosen]

    def take(self, query, seconds, fmt):
        target = config.SHORT_SHOT_SECONDS if fmt == "short" else config.LONG_SHOT_SECONDS
        n = max(1, round(seconds / target))
        if len(self.unused) < n:
            self.unused = list(range(len(self.scenes)))  # start over rather than run dry
        qt = _tokens(query)

        N = len(self.scenes)
        best_of = lambda i: hook_score(self.scenes[i], i, N, "balanced")

        def score(i):
            d = _tokens(self.scenes[i].get("description", ""))
            return len(qt & d) / (len(qt | d) or 1) + 0.05 * best_of(i)  # matches the words AND is a strong moment

        ranked = sorted(self.unused, key=lambda i: (-score(i), self.scenes[i]["start"]))
        top = ranked[:n]
        first = max(top, key=best_of)  # the best part of the film comes first, so people stay
        chosen = [first] + sorted([i for i in top if i != first], key=lambda i: self.scenes[i]["start"])
        for i in chosen:
            self.unused.remove(i)
        each = seconds / len(chosen)
        return [self.shot(i, each) for i in chosen]


STYLE_TAGS = {
    "romance": {"kiss", "romance", "intimate"},
    "action": {"fight", "explosion", "chase", "action"},
    "shock": {"shock", "scare", "reveal"},
    "comedy": {"funny"},
    "emotional": {"emotional", "romance"},
}
MOOD_STYLE = {"comedy": "comedy", "romance": "romance", "action": "action", "drama": "emotional",
              "thriller": "shock", "suspense": "shock", "horror": "shock", "scifi": "balanced"}


def style_for_mood(mood):
    """Which kind of scene makes the strongest opening for this mood."""
    return MOOD_STYLE.get(mood, "balanced")
ANY_HOOK_TAGS = {"kiss", "fight", "explosion", "chase", "shock", "scare", "reveal", "intimate"}


def hook_score(scene, idx, n, style):
    """How strong this scene is as an opening shot. Uses the AI score when there is one, otherwise a cheap guess:
    trailers build to a climax, so later and shorter (faster-cut) scenes score higher."""
    base = scene.get("hook")
    if base is None:
        pos = idx / max(1, n - 1)
        base = 3 + 4 * max(0.0, min(1.0, (pos - 0.3) / 0.5)) + max(0.0, (3.5 - (scene["end"] - scene["start"]))) * 0.6
    tags = set(scene.get("tags") or [])
    bonus = 3.0 if tags & STYLE_TAGS.get(style, set()) else (1.5 if style == "balanced" and tags & ANY_HOOK_TAGS else 0.0)
    return base + bonus


def _find_pool(pools, name):
    if not name:
        return None
    n = name.lower().strip()
    for k, v in pools.items():
        if k == n or k in n or n in k:
            return v
    return None


def pick_visuals(segments, fmt, work: Path, trailers=None, extra_assets=None, use_stock=True, progress=lambda p: None, hook_style=None):
    """trailers: {movie title: trailer meta dict}. Preference per segment:
    1) that movie's trailer scenes  2) your library  3) stock footage  4) colour card."""
    style = hook_style or config.HOOK_STYLE
    if style == "auto":
        style = "balanced"
    pools = {t.lower().strip(): TrailerPool(m) for t, m in (trailers or {}).items()}
    pool_list = list(pools.values())
    matcher = Matcher(scan_library() + (extra_assets or []))
    dest = work / "stock"
    dest.mkdir(exist_ok=True)
    orientation = "portrait" if fmt == "short" else "landscape"
    intro_i = 0
    t0 = 0.0  # where this segment starts in the finished video
    hook_info = []
    for i, seg in enumerate(segments):
        q = (seg.get("visual_query") or "") + " " + seg["narration"]
        asset = None
        pool = _find_pool(pools, seg.get("movie"))
        if pool is None and not seg.get("movie") and pool_list:
            pool = pool_list[intro_i % len(pool_list)]  # intro/outro: a taste from each movie in turn
            intro_i += 1
        if pool is not None:
            hook_dur = min(seg["duration"], config.HOOK_SECONDS - t0) if (config.HOOK_ENABLED and t0 < config.HOOK_SECONDS) else 0
            shots = []
            if hook_dur >= 0.8:
                if seg.get("movie"):
                    shots = pool.take_hook(hook_dur, fmt, style)
                else:  # the opening line: the best scenes across ALL the movies in the video
                    per = 1.5 if fmt == "short" else 2.4
                    k = max(1, round(hook_dur / per))
                    allc = sorted(((sc, pl, ix) for pl in pool_list for sc, ix in pl.hook_candidates(style)),
                                  key=lambda x: -x[0])
                    top, seen_movies = [], {}
                    for sc, pl, ix in allc:  # spread over the movies so the hook shows variety
                        if seen_movies.get(id(pl), 0) < max(1, (k + 1) // 2) and len(top) < k:
                            top.append((sc, pl, ix)); seen_movies[id(pl)] = seen_movies.get(id(pl), 0) + 1
                    each = hook_dur / max(1, len(top))
                    for sc, pl, ix in top:
                        pl.unused.remove(ix) if ix in pl.unused else None
                        shots.append(pl.shot(ix, each))
                hook_info.append({"at": round(t0, 1), "scenes": len(shots)})
            rest = seg["duration"] - (hook_dur if shots else 0)
            if rest >= 0.6:
                shots += pool.take(q, rest, fmt)
            asset = {"kind": "montage", "shots": shots, "source": "trailer",
                     "license": "studio trailer (commentary use)", "movie": pool.meta["title"], "path": pool.meta["path"]}
        if asset is None:
            asset = matcher.best(seg.get("visual_query") or seg["narration"])
        if asset is None and use_stock:
            vq = seg.get("visual_query") or seg["narration"]
            asset = pexels_clip(vq, orientation, dest, i) or pixabay_clip(vq, dest, i, orientation)
        seg["asset"] = asset or {"path": "", "kind": "card", "source": "fallback_card", "license": "n/a"}
        t0 += seg["duration"]
        progress((i + 1) / len(segments))
    pick_visuals.last_hook = hook_info
    return segments
