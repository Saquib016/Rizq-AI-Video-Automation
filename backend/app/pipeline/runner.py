import json
import traceback

from .. import config, db, media
from . import assets, editor, ingest, music, script, thumbnails, trailers, voice


def _stage(job_id, name, lo, hi):
    """Return a callback that maps 0..1 inside a stage onto the overall progress bar."""
    db.update_job(job_id, stage=name, progress=lo)
    return lambda p: db.update_job(job_id, stage=name, progress=int(lo + (hi - lo) * max(0, min(1, p))))


def run_job(job_id):
    job = db.get_job(job_id)
    inp = job["input"]
    work = config.JOBS_DIR / job_id
    work.mkdir(parents=True, exist_ok=True)
    ai_before = db.total_ai_requests()
    db.update_job(job_id, status="running", error="")
    db.delete_used_for_job(job_id)  # a re-run must not be blocked by its own earlier movies
    try:
        media.require_ffmpeg()
        fmt = inp.get("format", "short")
        channel = inp.get("channel") or {}
        niche = channel.get("niche", "movie content")
        title = inp.get("title", "").strip()
        context, source_assets, source_info = None, [], None

        # 1. Ingest (link mode)
        if inp.get("mode") == "link":
            if not inp.get("rights_confirmed"):
                raise RuntimeError("Rights confirmation is required before downloading a source video.")
            cb = _stage(job_id, "Downloading source video", 0, 12)
            source_info = ingest.download_source(inp["url"], work / "source")
            cb(1)
            title = title or source_info["title"]
            context = source_info
            cb = _stage(job_id, "Analysing source scenes", 12, 22)
            source_assets = ingest.index_source_scenes(source_info["path"], work)
            cb(1)
        else:
            db.update_job(job_id, progress=22)

        # 2. Script
        _stage(job_id, "Writing script", 22, 30)
        sc = script.generate_script(title, fmt, inp.get("language") or channel.get("language", "English"),
                                    niche, context=context, source_scenes=source_assets,
                                    avoid=db.used_movies() if inp.get("unique_movies", True) else [],
                                    movie_mode=inp.get("movie_count", "auto"))
        segments = sc["segments"]
        (work / "script.json").write_text(json.dumps(sc, indent=2))

        # 2b. Trailers (one per movie, cached after the first download)
        trailer_meta, warnings = {}, []
        if inp.get("use_trailers"):
            n = max(1, len(sc.get("movies", [])))
            for k, mv in enumerate(sc.get("movies", [])):
                cb = _stage(job_id, f"Finding trailer: {mv['title']}", 30 + 12 * k / n, 30 + 12 * (k + 1) / n)
                try:
                    year = int(mv["year"]) if str(mv.get("year") or "").isdigit() else None
                    tm = trailers.prepare(mv["title"], year, cb,
                                          prefer_vertical=(fmt == "short" and config.PREFER_VERTICAL))
                    if ((sc.get("one_movie") and fmt == "long" and config.OFFICIAL_CLIPS) or (fmt == "short" and config.OFFICIAL_CLIPS_SHORTS)) and not tm.get("vertical"):
                        try:  # a long video about ONE film: add the studio's official clips, not only the trailer
                            extras = trailers.official_clips(mv["title"], year, config.TRAILERS / trailers.slug(mv["title"], year),
                                                      max_clips=1 if fmt == "short" else 2)
                            if extras:
                                tm = trailers.merged(tm, extras)
                        except Exception:
                            pass
                    trailer_meta[mv["title"]] = tm
                except Exception as e:
                    warnings.append(f"No trailer for '{mv['title']}': {str(e)[:160]}. Used other footage instead.")

        # 3. Voice
        cb = _stage(job_id, "Generating narration", 42, 56)
        voice_info = voice.synthesize(segments, inp.get("voice_id") or channel.get("voice_id"), work, cb, mood=music.normalize_mood(sc.get("mood")),
                                    provider=inp.get("voice_provider") or None,
                                    gender=(sc.get("gender") if sc.get("pov") == "protagonist" else None))
        if voice_info.get("fallback_reason"):
            warnings.append("ElevenLabs credits ran out, so this video used the free Edge voice instead. "
                            "Add credits or switch the voice in the form to use ElevenLabs again.")

        # 3b. Hard time limit: speed the voice up a little (max 1.2x) if the script ran long
        cap = config.SINGLE_MAX_SECONDS if sc.get("single") else (config.SHORT_MAX_SECONDS if fmt == "short" else config.LONG_MAX_SECONDS)
        fit = voice.fit_to_limit(segments, cap, work)
        if fit["factor"] > 1.0:
            warnings.append(f"The voice was sped up {fit['factor']}x so the video ends within {cap} seconds.")
        if fit["total"] > cap + 1:
            warnings.append(f"The video is {fit['total']} s, over the {cap} s limit. Lower the word targets in Settings > Video length.")

        # 4. Visuals
        cb = _stage(job_id, "Matching scenes to the script", 56, 62)
        assets.pick_visuals(segments, fmt, work, trailers=trailer_meta, extra_assets=source_assets,
                            use_stock=inp.get("use_pexels", True), progress=cb,
                            hook_style=(assets.style_for_mood(music.normalize_mood(sc.get("mood")))
                                        if config.HOOK_STYLE == "auto" else config.HOOK_STYLE))

        # 5. Music + edit
        _stage(job_id, "Choosing background music", 62, 64)
        total = sum(s["duration"] for s in segments)
        music_path, music_note = music.pick(sc.get("mood"), total, work)
        cb = _stage(job_id, "Editing video", 64, 85)
        final = editor.render(segments, fmt, work, cb, music=music_path, movies=sc.get("movies"))

        # 6. Thumbnails
        if fmt == "short" and not config.SHORT_THUMBNAILS:
            thumbs = []  # Shorts skip thumbnails (turn on in Settings if you want them)
        else:
            cb = _stage(job_id, "Creating thumbnails", 85, 99)
            thumbs = thumbnails.generate(sc, niche, final, work, cb)

        meta_out = {"title": sc["title"], "description": sc["description"], "tags": sc.get("tags", []),
                    "instagram_caption": sc.get("instagram_caption") or sc["description"],
                    "facebook_title": sc.get("facebook_title") or sc["title"],
                    "facebook_description": sc.get("facebook_description") or sc["description"]}
        if trailer_meta:
            credits = "\n\nMovie footage: official trailers, © their respective studios, shown for commentary and review.\n" + \
                      "\n".join(f"- {t}: {m['url']}" for t, m in trailer_meta.items())
            meta_out["description"] = (meta_out["description"] + credits)[:4900]
            meta_out["facebook_description"] = (meta_out["facebook_description"] + "\n\nTrailer footage © the studios, used for commentary.")[:4900]
        result = {
            "video": "final.mp4",
            "duration": round(total, 1),
            "format": fmt,
            "metadata": meta_out,
            "mood": music.normalize_mood(sc.get("mood")),
            "music": music_note,
            "trailers": [{"movie": t, "url": m["url"], "video_title": m["video_title"], "channel": m["channel"], "vertical": bool(m.get("vertical")), "extras": m.get("extra_clips", [])}
                         for t, m in trailer_meta.items()],
            "warnings": warnings,
            "single_movie": bool(sc.get("single")),
            "pov": sc.get("pov"), "protagonist": sc.get("protagonist"), "hook_options": sc.get("hook_options") or [],
            "time_limit": cap, "final_seconds": fit["total"], "published": {}, "trends": sc.get("trends", []),
            "ai_requests": max(0, db.total_ai_requests() - ai_before),
            "hook": getattr(assets.pick_visuals, "last_hook", []) if config.HOOK_ENABLED and trailer_meta else [],
            "quality": "%dx%d" % config.output_size(fmt),
            "segments": [{"narration": s["narration"], "visual_query": s.get("visual_query", ""), "movie": s.get("movie"),
                          "asset_source": s["asset"]["source"], "asset_license": s["asset"].get("license", ""),
                          "asset_credit": s["asset"].get("credit", "")} for s in segments],
            "thumbnails": thumbs,
            "selected_thumbnail": (next((t["file"] for t in thumbs if t["recommended"]), thumbs[0]["file"]) if thumbs else ""),
            "silent_dryrun": voice_info["silent_dryrun"],
            "source": {k: source_info[k] for k in ("url", "title", "uploader", "license")} if source_info else None,
            "upload": None,
        }
        db.add_used_movies([{"title": m["title"], "year": int(m["year"]) if str(m.get("year") or "").isdigit() else None}
                            for m in sc.get("movies", [])], job_id)
        db.update_job(job_id, status="review", stage="Ready for review", progress=100, result=result)
    except Exception as e:
        traceback.print_exc()
        db.update_job(job_id, status="failed", stage="Failed", error=str(e)[:2000])
