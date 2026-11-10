"""Instagram Reels and Facebook (Page Reels / Page videos) publishing through the Meta Graph API.
YouTube uploads stay in youtube.py. Needs a Page access token, the Facebook Page ID and the Instagram professional account ID."""
import time
from pathlib import Path

import requests

from .. import config, media


def status():
    ok = bool(config.META_ACCESS_TOKEN)
    return {"instagram": ok and bool(config.IG_USER_ID), "facebook": ok and bool(config.FB_PAGE_ID)}


def _graph(path):
    return f"https://graph.facebook.com/{config.META_GRAPH_VERSION}/{path}"


HINTS = {
    200: "The token is not allowed to post on this Page. Use the PAGE access token (not your personal user token), made with pages_manage_posts "
         "(and publish_video if listed) and with your Page ticked, by an account that has full control of the Page.",
    190: "The token is invalid or has expired. Make a new one and paste the Page token again.",
    10: "A permission is missing. Generate the token again and tick every permission.",
    100: "Check the Page ID / Instagram ID and that the token can see that Page.",
    368: "Facebook blocked the action for now (spam or policy check). Wait and try again later.",
}


def _err(r):
    try:
        e = r.json().get("error", {})
        hint = HINTS.get(e.get("code"), "")
        return f"{e.get('message') or r.text[:200]} (code {e.get('code')}, subcode {e.get('error_subcode')})" + (f" Hint: {hint}" if hint else "")
    except Exception:
        return r.text[:300]


def make_social_copy(src: Path, dst: Path, vertical: bool):
    """A lighter 1080p copy for Instagram/Facebook (they re-encode anyway; smaller files upload faster and fit their limits)."""
    vf = "scale=1080:-2" if vertical else "scale=-2:1080"
    media.run(["ffmpeg", "-y", "-i", src, "-vf", vf, "-r", "30", "-c:v", "libx264", "-preset", "fast", "-crf", "21",
               "-maxrate", "10M", "-bufsize", "20M", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
               "-movflags", "+faststart", dst])
    return dst


def publish_instagram(video: Path, caption: str, fmt="short"):
    if fmt != "short":
        raise RuntimeError("Instagram Reels are vertical and short, so long landscape videos are not sent to Instagram.")
    if not status()["instagram"]:
        raise RuntimeError("Instagram is not set up. Add the access token and Instagram account ID in Settings > Social accounts.")
    token, ig, ver = config.META_ACCESS_TOKEN, config.IG_USER_ID, config.META_GRAPH_VERSION
    r = requests.post(_graph(f"{ig}/media"), timeout=60, data={
        "media_type": "REELS", "upload_type": "resumable", "caption": caption[:2200], "share_to_feed": "true", "access_token": token})
    if r.status_code != 200:
        raise RuntimeError("Instagram: " + _err(r))
    cid = r.json()["id"]
    size = video.stat().st_size
    with open(video, "rb") as fh:
        up = requests.post(f"https://rupload.facebook.com/ig-api-upload/{ver}/{cid}", timeout=1800, data=fh,
                           headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)})
    if up.status_code != 200:
        raise RuntimeError("Instagram upload: " + _err(up))
    for _ in range(72):  # wait up to 6 minutes for Instagram to process the video
        s = requests.get(_graph(cid), params={"fields": "status_code,status", "access_token": token}, timeout=30).json()
        code = s.get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram could not process the video: {s.get('status') or code}")
        time.sleep(5)
    else:
        raise RuntimeError("Instagram is still processing the video. Try publishing again in a few minutes.")
    pub = requests.post(_graph(f"{ig}/media_publish"), data={"creation_id": cid, "access_token": token}, timeout=60)
    if pub.status_code != 200:
        raise RuntimeError("Instagram publish: " + _err(pub))
    mid = pub.json()["id"]
    link = ""
    try:
        link = requests.get(_graph(mid), params={"fields": "permalink", "access_token": token}, timeout=30).json().get("permalink", "")
    except Exception:
        pass
    return {"id": mid, "url": link}


def publish_facebook(video: Path, title: str, description: str, fmt="short"):
    if not status()["facebook"]:
        raise RuntimeError("Facebook is not set up. Add the access token and Page ID in Settings > Social accounts.")
    token, page, ver = config.META_ACCESS_TOKEN, config.FB_PAGE_ID, config.META_GRAPH_VERSION
    if fmt == "short":  # a Page Reel
        r = requests.post(_graph(f"{page}/video_reels"), data={"upload_phase": "start", "access_token": token}, timeout=60)
        if r.status_code != 200:
            raise RuntimeError("Facebook: " + _err(r))
        vid, upload_url = r.json()["video_id"], r.json()["upload_url"]
        with open(video, "rb") as fh:
            up = requests.post(upload_url, timeout=1800, data=fh,
                               headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(video.stat().st_size)})
        if up.status_code != 200:
            raise RuntimeError("Facebook upload: " + _err(up))
        fin = requests.post(_graph(f"{page}/video_reels"), timeout=120, data={
            "video_id": vid, "upload_phase": "finish", "video_state": "PUBLISHED",
            "title": title[:100], "description": description[:2000], "access_token": token})
        if fin.status_code != 200:
            raise RuntimeError("Facebook publish: " + _err(fin))
        return {"id": vid, "url": f"https://www.facebook.com/reel/{vid}"}
    with open(video, "rb") as fh:  # long landscape video: a normal Page video
        r = requests.post(_graph(f"{page}/videos"), timeout=3600, files={"source": (video.name, fh, "video/mp4")},
                          data={"title": title[:100], "description": description[:5000], "published": "true", "access_token": token})
    if r.status_code != 200:
        raise RuntimeError("Facebook: " + _err(r))
    vid = r.json()["id"]
    return {"id": vid, "url": f"https://www.facebook.com/{page}/videos/{vid}"}


def test_connection():
    """Checks the token and IDs without posting anything."""
    out = {}
    if not config.META_ACCESS_TOKEN:
        return {"token": {"ok": False, "error": "No access token yet."}}
    try:
        r = requests.get(_graph("me"), params={"fields": "id,name", "access_token": config.META_ACCESS_TOKEN}, timeout=30)
        if r.status_code == 200:
            j = r.json()
            is_page = bool(config.FB_PAGE_ID) and j.get("id") == config.FB_PAGE_ID
            out["token"] = {"ok": is_page or not config.FB_PAGE_ID, "detail": f"{j.get('name', '')} ({'Page token: good' if is_page else 'this is a USER token, not a Page token'})",
                            "error": "" if is_page else "This is a user token. Posting needs the PAGE token: run me/accounts (or PAGE_ID?fields=access_token) and use that access_token."}
        else:
            out["token"] = {"ok": False, "detail": _err(r)}
    except Exception as e:
        out["token"] = {"ok": False, "error": str(e)[:200]}
    for key, ident, field in (("facebook", config.FB_PAGE_ID, "name"), ("instagram", config.IG_USER_ID, "username")):
        if not ident:
            out[key] = {"ok": False, "error": "ID not set."}
            continue
        try:
            r = requests.get(_graph(ident), params={"fields": field, "access_token": config.META_ACCESS_TOKEN}, timeout=30)
            out[key] = {"ok": r.status_code == 200, "detail": r.json().get(field, "") if r.status_code == 200 else _err(r)}
        except Exception as e:
            out[key] = {"ok": False, "error": str(e)[:200]}
    return out
