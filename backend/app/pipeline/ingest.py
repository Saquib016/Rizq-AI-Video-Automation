"""Link mode: fetch a source video you have the rights to use, read its metadata/captions,
and split it into captioned scenes the editor can reuse as footage."""
import re
from pathlib import Path

from .. import config, llm, media


def download_source(url: str, dest: Path) -> dict:
    """Download a video + English captions with yt-dlp.

    Only call this for videos you own, have a licence for, or that are Creative Commons / public domain.
    The API layer refuses to run it unless the user ticked the rights confirmation.
    """
    import yt_dlp

    dest.mkdir(parents=True, exist_ok=True)
    opts = {
        "outtmpl": str(dest / "source.%(ext)s"),
        "format": "bv*[height<=1080]+ba/b[height<=1080]/b",
        "merge_output_format": "mp4",
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en.*", "en"],
        "subtitlesformat": "vtt",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)

    video = next(iter(sorted(dest.glob("source.mp4"))), None) or next(
        (p for p in dest.glob("source.*") if p.suffix not in (".vtt", ".json")), None
    )
    if not video:
        raise RuntimeError("Download finished but no video file was found.")

    transcript = ""
    vtt = next(iter(sorted(dest.glob("source*.vtt"))), None)
    if vtt:
        transcript = _vtt_to_text(vtt.read_text(encoding="utf-8", errors="ignore"))

    return {
        "path": video,
        "title": info.get("title", ""),
        "description": (info.get("description") or "")[:2000],
        "uploader": info.get("uploader", ""),
        "license": info.get("license") or "unspecified",
        "duration": info.get("duration") or media.duration(video),
        "transcript": transcript[:12000],
        "url": url,
    }


def _vtt_to_text(vtt: str) -> str:
    lines, last = [], ""
    for line in vtt.splitlines():
        line = line.strip()
        if not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")) or "-->" in line:
            continue
        line = re.sub(r"<[^>]+>", "", line)
        if line and line != last:
            lines.append(line)
            last = line
    return " ".join(lines)


def index_source_scenes(video: Path, work: Path, max_scenes=30) -> list:
    """Cut the source into windows, caption one keyframe per window with a vision model.
    Returns asset dicts with start/end so the editor can reuse each window as a clip."""
    total = media.duration(video)
    window = max(4.0, total / max_scenes)
    frames_dir = work / "frames"
    frames_dir.mkdir(exist_ok=True)

    scenes, t, i = [], 0.0, 0
    while t < total - 1.0:
        end = min(total, t + window)
        mid = (t + end) / 2
        f = frames_dir / f"f{i:03d}.jpg"
        media.extract_frame(str(video), str(f), mid, width=640)
        scenes.append({"path": str(video), "kind": "video_segment", "start": round(t, 2),
                       "end": round(end, 2), "frame": str(f), "description": "",
                       "source": "user_source", "license": "confirmed_by_user"})
        t, i = end, i + 1

    if llm.available():
        for b in range(0, len(scenes), 8):
            batch = scenes[b:b + 8]
            try:
                out = llm.ask_json(
                    "You describe video frames for a stock-footage search index.",
                    f"Describe each of the {len(batch)} images in order, in one factual sentence each "
                    "(setting, subjects, action, mood). Return a JSON array of strings.",
                    images=[s["frame"] for s in batch],
                    model=config.ANTHROPIC_VISION_MODEL,
                    max_tokens=1500,
                )
                for s, d in zip(batch, out):
                    s["description"] = str(d)
            except Exception:
                pass  # scenes without descriptions still work as fallback footage
    return scenes
