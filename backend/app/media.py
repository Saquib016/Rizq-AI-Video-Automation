"""Small wrappers around ffmpeg / ffprobe."""
import json
import shutil
import subprocess
from pathlib import Path

from . import config


def require_ffmpeg():
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise RuntimeError(
                f"{tool} not found. Install FFmpeg and make sure it is on your PATH "
                "(see README, step 2)."
            )


def run(cmd, cwd=None):
    p = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True)
    if p.returncode != 0:
        tail = "\n".join(p.stderr.strip().splitlines()[-12:])
        raise RuntimeError(f"Command failed: {' '.join(str(c) for c in cmd[:3])} ...\n{tail}")
    return p


def duration(path) -> float:
    p = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path])
    return float(json.loads(p.stdout)["format"]["duration"])


def has_video_stream(path) -> bool:
    p = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_type", "-of", "json", path])
    return bool(json.loads(p.stdout).get("streams"))


def extract_frame(video, out_jpg, at_seconds, width=960):
    run(["ffmpeg", "-y", "-ss", f"{at_seconds:.2f}", "-i", video, "-frames:v", "1",
         "-vf", f"scale={width}:-2", "-q:v", "3", out_jpg])
    return Path(out_jpg)


_ENC = None


def best_encoder() -> str:
    """The graphics card's H.264 encoder if it really works on this PC (much faster), otherwise libx264."""
    global _ENC
    if _ENC is not None:
        return _ENC
    _ENC = "libx264"
    if config.HW_ENCODE:
        for name in ("h264_nvenc", "h264_qsv", "h264_amf", "h264_videotoolbox"):
            p = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                                "color=c=black:s=1280x720:d=0.2:r=30", "-c:v", name, "-f", "null", "-"],
                               capture_output=True)
            if p.returncode == 0:
                _ENC = name
                break
    return _ENC


def video_encode_args(width, height):
    """Encoder settings sized for YouTube: about 40 Mbit/s at 4K, 16 at 1440p, 10 at 1080p."""
    enc = best_encoder()
    big = max(width, height)
    mbps = 40 if big >= 3000 else 16 if big >= 2000 else 10
    tags = ["-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]
    if enc == "h264_nvenc":
        return ["-c:v", enc, "-preset", "p4", "-rc", "vbr", "-cq", "19", "-b:v", f"{mbps}M", "-maxrate", f"{mbps * 3 // 2}M", "-bufsize", f"{mbps * 2}M", *tags]
    if enc == "h264_qsv":
        return ["-c:v", enc, "-global_quality", "20", "-b:v", f"{mbps}M", *tags]
    if enc == "h264_amf":
        return ["-c:v", enc, "-quality", "balanced", "-rc", "vbr_peak", "-b:v", f"{mbps}M", "-maxrate", f"{mbps * 3 // 2}M", *tags]
    if enc == "h264_videotoolbox":
        return ["-c:v", enc, "-b:v", f"{mbps}M", *tags]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-profile:v", "high", *tags]
