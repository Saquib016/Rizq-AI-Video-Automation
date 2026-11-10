"""Background music by mood.

Order (setting MUSIC_SOURCE=auto):
  1. tracks you put in assets/music/<mood>/ (your own music always wins)
  2. otherwise free, no-attribution (CC0 / public domain) music downloaded once from Openverse and kept in that folder
  3. otherwise a soft pad generated with FFmpeg (no copyright, no download)
"""
import json
import random
import re
from pathlib import Path

import requests

from .. import config, media

ALIASES = {
    "suspense": "suspense", "mystery": "suspense", "psychological": "suspense", "noir": "suspense",
    "thriller": "thriller", "crime": "thriller", "spy": "thriller",
    "horror": "horror", "scary": "horror", "supernatural": "horror",
    "action": "action", "adventure": "action", "war": "action", "superhero": "action",
    "drama": "drama", "emotional": "drama", "sad": "drama", "biopic": "drama",
    "romance": "romance", "romantic": "romance", "love": "romance",
    "scifi": "scifi", "sci-fi": "scifi", "science fiction": "scifi", "fantasy": "scifi",
    "comedy": "comedy", "funny": "comedy", "fun": "comedy",
}
MOODS = sorted(set(ALIASES.values()))
AUDIO_EXT = (".mp3", ".wav", ".m4a", ".ogg", ".flac")

# What to search for when downloading free music
SEARCH = {
    "suspense": ["suspense cinematic", "dark ambient tension", "mystery underscore"],
    "thriller": ["thriller cinematic", "dark pulse tension", "chase underscore"],
    "horror": ["horror ambient", "creepy dark drone", "scary cinematic"],
    "action": ["action cinematic drums", "epic trailer", "driving energetic"],
    "drama": ["emotional piano", "sad cinematic strings", "dramatic piano"],
    "romance": ["romantic piano", "love theme soft", "tender piano"],
    "scifi": ["futuristic ambient", "sci-fi electronic cinematic", "space ambient"],
    "comedy": ["funny playful", "quirky comedy", "happy ukulele"],
}


# ---------------------------------------------------------------- generated pads (fallback)
def _saw(f, amp):
    return "+".join(f"{amp}*(2*mod({f * d:.3f}*t,1)-1)" for d in (0.994, 1.0, 1.006))  # three slightly detuned saws = a warm, wide pad


def _pad(freqs, amp=0.04):
    return "+".join(_saw(f, amp) for f in freqs)


HEART = "+0.55*pow(0.5+0.5*sin(2*PI*1.15*t),14)*sin(2*PI*100*t)"
KICK = "+0.6*exp(-9*mod(t,0.5))*sin(2*PI*85*t)+0.05*(2*mod(82.41*t,1)-1)*pow(0.5+0.5*sin(2*PI*4*t),2)"
PLUCK = ("+0.4*exp(-9*mod(t*3,1))*(1-exp(-120*mod(t*3,1)))*sin(2*PI*if(lt(mod(t*3,4),1),261.63,if(lt(mod(t*3,4),2),329.63,"
         "if(lt(mod(t*3,4),3),392,329.63)))*t)")
GEN = {  # chord notes (Hz) + extra layer + filter chain. Everything is low-passed so no thin, buzzing high notes are left.
    "suspense": ([55, 110, 130.81, 164.81], "", "lowpass=f=800,lowpass=f=800,tremolo=f=0.12:d=0.35,aecho=0.8:0.7:90|200:0.4|0.3"),
    "thriller": ([73.42, 110, 130.81, 174.61], HEART, "lowpass=f=900,lowpass=f=900,tremolo=f=0.15:d=0.3,aecho=0.8:0.6:80|160:0.35|0.25"),
    "horror": ([55, 110, 116.54, 164.81, 174.61], "", "lowpass=f=700,lowpass=f=700,tremolo=f=0.2:d=0.45,aecho=0.8:0.8:120|260:0.45|0.35"),
    "action": ([82.41, 123.47, 164.81, 246.94], KICK, "lowpass=f=1500,lowpass=f=1500,acompressor=threshold=0.2:ratio=3"),
    "drama": ([110, 130.81, 164.81, 196], "", "lowpass=f=1100,lowpass=f=1100,tremolo=f=0.1:d=0.25,aecho=0.8:0.7:100|220:0.4|0.3"),
    "romance": ([130.81, 164.81, 196, 246.94], "", "lowpass=f=1300,lowpass=f=1300,tremolo=f=0.1:d=0.2,aecho=0.8:0.7:100|220:0.4|0.3"),
    "scifi": ([110, 164.81, 246.94, 329.63], "", "lowpass=f=1200,lowpass=f=1200,tremolo=f=0.18:d=0.4,aecho=0.8:0.8:110|240:0.45|0.35"),
    "comedy": ([130.81, 196], PLUCK, "lowpass=f=3500,aecho=0.7:0.5:60:0.25"),
}


def generate(mood, seconds, out):
    dur = max(10, int(seconds) + 4)
    notes, extra, chain = GEN[mood]
    expr = _pad(notes, 0.03 if mood == "comedy" else 0.04) + extra
    flt = f"{chain},afade=t=in:d=2,afade=t=out:st={dur - 3}:d=3,loudnorm=I=-23:LRA=7:TP=-2"
    media.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"aevalsrc='{expr}':s=44100:d={dur}", "-af", flt, "-ac", "2", str(out)])
    return out


def make_hit(out):
    """A short, deep bass hit with a little noise (royalty-free, generated) that lands on the very first frame."""
    media.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
               "aevalsrc='0.9*exp(-5*t)*sin(2*PI*(42+95*exp(-14*t))*t)+0.22*exp(-10*t)*(random(0)-0.5)*2':s=44100:d=1.4",
               "-af", "lowpass=f=6000,alimiter=limit=0.9", "-ac", "2", str(out)])
    return out


# ---------------------------------------------------------------- real free music (Openverse, CC0 / public domain only)
def fetch_free_track(mood, folder: Path):
    """Downloads one no-attribution music track for this mood and keeps it in the mood folder. Returns the path or None."""
    folder.mkdir(parents=True, exist_ok=True)
    have = {p.name for p in folder.glob("auto_*")}
    for q in SEARCH.get(mood, []):
        try:
            r = requests.get("https://api.openverse.org/v1/audio/", timeout=25, headers={"User-Agent": "CineForge/1.0"},
                             params={"q": q, "license": "cc0,pdm", "category": "music", "page_size": 20})
            if r.status_code != 200:
                continue
            for it in r.json().get("results", []):
                url = it.get("url") or ""
                ext = Path(url.split("?")[0]).suffix.lower()
                name = f"auto_{it.get('id', '')[:12]}{ext if ext in AUDIO_EXT else '.mp3'}"
                if not url or name in have or (it.get("duration") and it["duration"] < 25000):
                    continue
                try:
                    dl = requests.get(url, timeout=60, stream=True, headers={"User-Agent": "CineForge/1.0"})
                    if dl.status_code != 200 or int(dl.headers.get("content-length", 0) or 0) > 30_000_000:
                        continue
                    path = folder / name
                    path.write_bytes(dl.content)
                    if media.duration(path) < 25:
                        path.unlink(missing_ok=True)
                        continue
                    path.with_suffix(".json").write_text(json.dumps({
                        "title": it.get("title"), "creator": it.get("creator"), "license": it.get("license"), "source": it.get("foreign_landing_url")}))
                    return path
                except Exception:
                    continue
        except Exception:
            continue
    return None


def normalize_mood(mood):
    m = (mood or "").lower().strip()
    if m in ALIASES:
        return ALIASES[m]
    for k, v in ALIASES.items():
        if k in m:
            return v
    return "drama"


def _tracks(mood):
    folder = config.MUSIC / mood
    pool = [p for p in folder.glob("*") if p.suffix.lower() in AUDIO_EXT] if folder.is_dir() else []
    if not pool:
        pool = [p for p in config.MUSIC.glob("*") if p.suffix.lower() in AUDIO_EXT]  # untagged tracks of yours
    return pool


def pick(mood, seconds, work):
    """Returns (path, description of where it came from)."""
    mood = normalize_mood(mood)
    src = config.MUSIC_SOURCE
    if src != "generated":
        tracks = _tracks(mood)
        mine = [t for t in tracks if not t.name.startswith("auto_")]
        if src == "auto" and not mine and len([t for t in tracks if t.name.startswith("auto_")]) < 3:
            new = fetch_free_track(mood, config.MUSIC / mood)  # build a small, varied set once; it is reused afterwards
            if new:
                tracks.append(new)
        if tracks:
            t = random.choice(mine or tracks)
            kind = "your track" if t in mine else "free no-attribution track"
            return t, f"{kind} '{t.name}' ({mood})"
    out = work / "music.wav"
    generate(mood, seconds, out)
    return out, f"generated {mood} pad (copyright-free)"
