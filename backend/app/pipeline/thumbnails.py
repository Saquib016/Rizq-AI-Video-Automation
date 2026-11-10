"""Generate 4 thumbnail candidates, then have Claude pick the one most likely to get clicks.

With OPENAI_API_KEY: AI-generated artwork (no text in the image), headline added with Pillow.
Without it: 4 well-chosen frames from the finished video, styled the same way.
"""
import base64
import random
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance

from .. import config, llm, media

W, H = 1280, 720
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/impact.ttf",
]


def _font(size):
    for p in [config.FONT_PATH, *FONT_CANDIDATES]:
        if p and Path(p).exists():
            return ImageFont.truetype(p, size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _as_list(x):
    """Models sometimes wrap a list in an object, e.g. {"concepts": [...]}."""
    if isinstance(x, dict):
        for v in x.values():
            if isinstance(v, list):
                return v
        return []
    return x if isinstance(x, list) else []


def concepts(script, niche):
    raw = llm.ask_json(
        "You are a YouTube thumbnail strategist who understands click-through rate.",
        f"""Video title: {script['title']}
Channel niche: {niche}
Narration summary: {' '.join(s['narration'] for s in script['segments'])[:1500]}

Create 4 DIFFERENT thumbnail concepts (different emotion / composition / colour mood).
Rules: headline max 4 words, bold and curiosity-driven; image_prompt describes ONLY the artwork, with no text,
no logos, no real people's likeness and no copyrighted characters; one clear focal subject; high contrast.
Also predict how well each would perform as a click-through (1 to 10) with a short reason, as an expert would.
Return JSON: [{{"headline": "...", "image_prompt": "...", "accent": "#RRGGBB", "ctr": 7, "why": "..."}}]""",
        max_tokens=1500,
    )
    out = [c for c in _as_list(raw) if isinstance(c, dict) and c.get("headline")]
    if not out:
        raise RuntimeError("no usable thumbnail concepts")
    return out[:4]


def _openai_image(prompt, out: Path):
    r = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
        json={"model": config.OPENAI_IMAGE_MODEL, "prompt": prompt + " Cinematic, dramatic lighting, 16:9, no text.",
              "size": "1536x1024", "n": 1},
        timeout=180,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Image API error {r.status_code}: {r.text[:200]}")
    item = r.json()["data"][0]
    if item.get("b64_json"):
        out.write_bytes(base64.b64decode(item["b64_json"]))
    else:
        out.write_bytes(requests.get(item["url"], timeout=60).content)


def _cover(img: Image.Image):
    scale = max(W / img.width, H / img.height)
    img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    l, t = (img.width - W) // 2, (img.height - H) // 2
    return img.crop((l, t, l + W, t + H))


def _compose(base_path: Path, headline: str, accent: str, out: Path):
    img = _cover(Image.open(base_path).convert("RGB"))
    img = ImageEnhance.Contrast(img).enhance(1.15)
    img = ImageEnhance.Color(img).enhance(1.2)

    # left-side shade so text stays readable
    shade = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(shade)
    for x in range(W):
        d.line([(x, 0), (x, H)], fill=int(max(0, 190 * (1 - x / (W * 0.75)))))
    img = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), img, shade)

    draw = ImageDraw.Draw(img)
    words = headline.upper().split()
    lines = [" ".join(words[:2]), " ".join(words[2:])] if len(words) > 2 else [" ".join(words)]
    lines = [l for l in lines if l]
    size = 150
    font = _font(size)
    while size > 60 and max(draw.textlength(l, font=font) for l in lines) > W * 0.62:
        size -= 6
        font = _font(size)
    y = H // 2 - int(len(lines) * size * 0.6)
    for k, line in enumerate(lines):
        fill = accent if k == len(lines) - 1 and len(lines) > 1 else "#FFFFFF"
        draw.text((60, y), line, font=font, fill=fill, stroke_width=8, stroke_fill="black")
        y += int(size * 1.12)
    img.save(out, "JPEG", quality=92)


def _frames(video: Path, work: Path, n=4):
    total = media.duration(video)
    positions = [total * p for p in (0.12, 0.35, 0.6, 0.85)][:n]
    out = []
    for i, t in enumerate(positions):
        f = work / f"frame{i}.jpg"
        media.extract_frame(str(video), str(f), t, width=1280)
        out.append(f)
    return out


def _normalize_rank(res, n):
    """Accepts the shapes models actually return and gives {"scores", "best_index", "reasons"} or None."""
    scores, reasons, best = None, None, None
    if isinstance(res, dict):
        scores = res.get("scores")
        reasons = res.get("reasons")
        best = res.get("best_index")
        if scores is None:  # e.g. {"thumbnails": [{"score": 8, "reason": "..."}]}
            res = _as_list(res)
    if isinstance(res, list):
        if res and all(isinstance(x, (int, float)) for x in res):
            scores = res
        elif res and all(isinstance(x, dict) for x in res):
            scores = [x.get("score") for x in res]
            reasons = [x.get("reason", "") for x in res]
    if not isinstance(scores, list) or not scores:
        return None
    nums = []
    for x in scores[:n]:
        try:
            nums.append(float(x))
        except (TypeError, ValueError):
            nums.append(0.0)
    nums += [0.0] * (n - len(nums))
    if not isinstance(reasons, list):
        reasons = []
    reasons = [str(r) for r in reasons[:n]] + [""] * (n - len(reasons[:n]))
    try:
        best = int(best)
    except (TypeError, ValueError):
        best = None
    if best is None or not 0 <= best < n:
        best = max(range(n), key=lambda i: nums[i])
    return {"scores": nums, "best_index": best, "reasons": reasons}


def _rank(files, script):
    try:
        small = []
        for f in files:
            im = Image.open(f)
            im.thumbnail((640, 360))
            p = f.with_name(f.stem + "_small.jpg")
            im.save(p, "JPEG", quality=80)
            small.append(p)
        res = llm.ask_json(
            "You are an expert at YouTube thumbnail click-through rate.",
            f"Video title: {script['title']}\nRate these {len(files)} thumbnails (in order) from 1-10 on: "
            "readability at phone size, emotional pull, clarity of focal point, and fit with the title. "
            'Return JSON: {"scores": [numbers], "best_index": 0, "reasons": ["short reason each"]}',
            images=small, model=config.ANTHROPIC_VISION_MODEL, max_tokens=800,
        )
        for p in small:
            p.unlink(missing_ok=True)
        return _normalize_rank(res, len(files))
    except Exception:
        return None


def generate(script, niche, video: Path, work: Path, progress=lambda p: None):
    out_dir = work / "thumbs"
    out_dir.mkdir(exist_ok=True)
    try:
        cons = concepts(script, niche)
    except Exception:
        cons = [{"headline": script["title"][:24], "image_prompt": script["title"], "accent": "#FFD23F"}] * 4
    fallback_frames = None
    files, meta = [], []

    for i, c in enumerate(cons):
        base = out_dir / f"base{i}.png"
        used = "ai"
        try:
            if not config.OPENAI_API_KEY:
                raise RuntimeError("no image key")
            _openai_image(c["image_prompt"], base)
        except Exception:
            used = "frame"
            if fallback_frames is None:
                fallback_frames = _frames(video, out_dir, len(cons))
            base = fallback_frames[i % len(fallback_frames)]
        out = out_dir / f"thumb{i + 1}.jpg"
        _compose(base, c["headline"], c.get("accent", "#FFD23F"), out)
        files.append(out)
        meta.append({"headline": c["headline"], "source": used})
        progress((i + 1) / (len(cons) + 1))

    rank = _rank(files, script) if config.RANK_THUMBNAILS else None  # extra AI request, off in budget mode
    if rank is None:  # use the click predictions that came with the ideas
        scores = []
        for c in cons[:len(files)]:
            try:
                scores.append(float(c.get("ctr")))
            except (TypeError, ValueError):
                scores.append(0.0)
        if any(scores):
            rank = {"scores": scores, "best_index": max(range(len(scores)), key=lambda i: scores[i]),
                    "reasons": [str(c.get("why", "")) for c in cons[:len(files)]]}
    best = rank["best_index"] if rank else 0
    result = []
    for i, (f, m) in enumerate(zip(files, meta)):
        result.append({
            "file": f.name, **m,
            "score": rank["scores"][i] if rank else None,
            "reason": rank["reasons"][i] if rank else "",
            "recommended": i == best,
        })
    progress(1.0)
    return result
