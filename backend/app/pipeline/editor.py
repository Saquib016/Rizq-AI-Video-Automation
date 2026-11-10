"""FFmpeg timeline builder: per-segment clips -> concat -> voice + music + burned captions."""
import random
import re
from pathlib import Path

from .. import config, media
from . import music as music_mod

FPS = 30
CARD_COLORS = ["0x16202b", "0x1d2b4a", "0x2a1f3d", "0x1f3a34"]


def _fmt_ts(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(segments, words_per_chunk, out: Path):
    lines, t, n = [], 0.0, 1
    for seg in segments:
        words = seg["narration"].split()
        speech = max(0.5, seg["duration"] - 0.25)
        chunks = [words[i:i + words_per_chunk] for i in range(0, len(words), words_per_chunk)] or [[]]
        total_chars = sum(len(" ".join(c)) for c in chunks) or 1
        ct = t
        for c in chunks:
            d = speech * len(" ".join(c)) / total_chars
            text = " ".join(c).strip()
            if text:
                lines += [str(n), f"{_fmt_ts(ct)} --> {_fmt_ts(ct + d)}", text, ""]
                n += 1
            ct += d
        t += seg["duration"]
    out.write_text("\n".join(lines), encoding="utf-8")


def _ass_time(t):
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    sec, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{sec:02d}.{cs:02d}"


def build_ass(segments, words_per_chunk, out: Path, fmt, movies=None):
    """Captions as an ASS file: normal captions at the bottom, and the HOOK line big, yellow, in the middle of the screen."""
    W, H = (1080, 1920) if fmt == "short" else (1920, 1080)
    font = Path(config.FONT_PATH).stem if config.FONT_PATH else "Arial"
    size, hsize, mv = (66, 104, 330) if fmt == "short" else (54, 80, 70)
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: %d\nPlayResY: %d\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, "
            "StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Default,%s,%d,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,5,0,2,60,60,%d,1\n"
            "Style: Hook,%s,%d,&H0000E5FF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,8,0,5,60,60,0,1\n"
            "Style: Title,%s,%d,&H002EB0FF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,7,0,8,60,60,%d,1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n") % (W, H, font, size, mv, font, hsize, font, (84 if fmt == "short" else 64), (250 if fmt == "short" else 60))
    lines, t = [], 0.0
    years = {(m.get("title") or "").lower(): m.get("year") for m in (movies or [])}
    order = []
    for idx, seg in enumerate(segments):
        mv = seg.get("movie")
        if mv and mv not in order:  # a title card the first time each movie appears: its name, clearly, on screen
            order.append(mv)
            yr = years.get(mv.lower())
            label = (f"{len({s.get('movie') for s in segments if s.get('movie')}) > 1 and str(len(order)) + '. ' or ''}{mv}").replace("{", "(").replace("}", ")").upper()
            label += f" ({yr})" if yr else ""
            lines.append(f"Dialogue: 1,{_ass_time(t)},{_ass_time(t + min(3.2, seg['duration']))},Title,,0,0,0,,{label}")
        words = seg["narration"].replace("{", "(").replace("}", ")").split()
        speech = max(0.5, seg["duration"] - 0.25)
        per = 3 if idx == 0 and fmt == "short" else words_per_chunk  # shorter chunks make the hook punchier
        chunks = [words[i:i + per] for i in range(0, len(words), per)] or [[]]
        total = sum(len(" ".join(c)) for c in chunks) or 1
        ct = t
        for c in chunks:
            d = speech * len(" ".join(c)) / total
            if c:
                text = " ".join(c).upper() if idx == 0 else " ".join(c)
                lines.append(f"Dialogue: 0,{_ass_time(ct)},{_ass_time(ct + d)},{'Hook' if idx == 0 else 'Default'},,0,0,0,,{text}")
            ct += d
        t += seg["duration"]
    out.write_text(head + "\n".join(lines) + "\n", encoding="utf-8")


def _vf(w, h):
    return f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h},fps={FPS},setsar=1,format=yuv420p"


def _src_size(path):
    import json
    p = media.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                   "stream=width,height", "-of", "json", path])
    st = json.loads(p.stdout)["streams"][0]
    return st["width"], st["height"]


ENC = ["-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS)]


def _shot(path, start, dur, w, h, fmt, out: Path):
    """One piece of footage.
    Vertical Short + landscape source: the footage is zoomed to fill SHORT_FILL (default 80%) of the screen height,
    centred (with a slow pan) over a blurred backdrop. Vertical sources simply fill the whole frame."""
    sw, sh = _src_size(path)
    base = ["ffmpeg", "-y", "-stream_loop", "-1", "-ss", f"{start}", "-i", path, "-t", f"{dur:.3f}"]
    if fmt == "short" and sw / sh > 1.2:
        fill = max(0.3, min(1.0, config.SHORT_FILL))
        fh = 2 * round(h * fill / 2)                       # height of the zoomed footage
        x = (f"(in_w-out_w)*(0.35+0.30*t/{max(dur, 0.5):.3f})" if config.SHORT_PAN else "(in_w-out_w)/2")
        fg = f"scale=-2:{fh}:flags=lanczos,crop={w}:{fh}:x='{x}':y=0"
        if fill >= 0.99:
            fc = f"[0:v]{fg},fps={FPS},setsar=1,format=yuv420p"
        else:
            bw, bh = 2 * round(w / 16), 2 * round(h / 16)
            fc = (f"[0:v]split[a][b];"
                  f"[a]scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh},boxblur=3:1,scale={w}:{h}[bg];"
                  f"[b]{fg}[fg];[bg][fg]overlay=0:(main_h-overlay_h)/2,fps={FPS},setsar=1,format=yuv420p")
        media.run([*base, "-filter_complex", fc, *ENC, str(out)])
    else:
        media.run([*base, "-vf", _vf(w, h), *ENC, str(out)])
    return out


def _clip(seg, i, w, h, fmt, work: Path):
    out = work / "clips" / f"clip{i:03d}.mp4"
    need = f"{seg['duration']:.3f}"
    asset = seg["asset"]
    kind, path = asset["kind"], asset.get("path", "")

    if kind == "montage":
        parts = [_shot(sh["path"], sh["start"], sh["dur"], w, h, fmt, work / "clips" / f"clip{i:03d}_{j}.mp4")
                 for j, sh in enumerate(asset["shots"])]
        lst = work / "clips" / f"clip{i:03d}.txt"
        lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts))
        media.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])
        return out
    if kind in ("video", "video_segment") and path:
        return _shot(path, asset.get("start", 0), seg["duration"], w, h, fmt, out)
    if kind == "image" and path:
        frames = int(seg["duration"] * FPS) + 2
        vf = (f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,crop={w*2}:{h*2},"
              f"zoompan=z='min(zoom+0.0009,1.25)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={FPS},"
              "setsar=1,format=yuv420p")
        media.run(["ffmpeg", "-y", "-i", path, "-t", need, "-vf", vf, *ENC, str(out)])
        return out
    color = CARD_COLORS[i % len(CARD_COLORS)]
    media.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:s={w}x{h}:d={need}:r={FPS}",
               "-vf", "format=yuv420p", *ENC, str(out)])
    return out


def render(segments, fmt, work: Path, progress=lambda p: None, music=None, movies=None):
    f = config.FORMATS[fmt]
    w, h = config.output_size(fmt) if config.CLIP_RES == "match" else (f["w"], f["h"])
    (work / "clips").mkdir(exist_ok=True)

    clip_files = []
    for i, seg in enumerate(segments):
        clip_files.append(_clip(seg, i, w, h, fmt, work))
        progress(0.5 * (i + 1) / len(segments))

    # concat video
    (work / "clips.txt").write_text("".join(f"file '{c.as_posix()}'\n" for c in clip_files))
    media.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(work / "clips.txt"),
               "-c", "copy", str(work / "video_nosound.mp4")])
    # concat voice
    (work / "voice.txt").write_text("".join(f"file '{Path(s['audio']).as_posix()}'\n" for s in segments))
    media.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(work / "voice.txt"),
               "-c", "copy", str(work / "voice.wav")])
    progress(0.65)

    build_ass(segments, f["caption_words"], work / "captions.ass", fmt, movies)
    ow, oh = config.output_size(fmt)
    # one high-quality upsize at the very end, light sharpening, then crisp captions at full size
    vf = f"scale={ow}:{oh}:flags=lanczos,unsharp=3:3:0.5:3:3:0.0,ass=captions.ass"

    inputs = ["-i", "video_nosound.mp4", "-i", "voice.wav"]
    norm = f"loudnorm=I={config.VOICE_LUFS}:TP=-1.5:LRA=11,aresample=44100"
    parts, extra_in, n = [f"[1:a]{norm}[v]"], [], 2
    labels = ["[v]"]
    if music:
        extra_in += ["-stream_loop", "-1", "-i", str(music)]
        parts.append(f"[{n}:a]{norm},volume={config.MUSIC_VOLUME}[m]"); labels.append("[m]"); n += 1
    if config.HOOK_SFX:  # a bass hit on the first frame; padded with silence so the mix level never changes
        extra_in += ["-i", str(music_mod.make_hit(work / "hit.wav"))]
        parts.append(f"[{n}:a]volume=0.55,apad[h]"); labels.append("[h]"); n += 1
    inputs += extra_in
    if len(labels) > 1:
        # all inputs are levelled first; amix halves/thirds the level, so it is multiplied back
        fc = ";".join(parts) + f";{''.join(labels)}amix=inputs={len(labels)}:duration=first:dropout_transition=0,volume={len(labels)},alimiter=limit=0.95[a]"
        amap = ["-filter_complex", fc, "-map", "0:v", "-map", "[a]"]
    else:
        amap = ["-map", "0:v", "-map", "1:a", "-af", f"{norm},alimiter=limit=0.95"]

    cmd = ["ffmpeg", "-y", *inputs, *amap, "-vf", vf, *media.video_encode_args(ow, oh),
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", "final.mp4"]
    media.run(cmd, cwd=work)  # cwd=work keeps the subtitles path simple on every OS
    progress(1.0)
    return work / "final.mp4"
