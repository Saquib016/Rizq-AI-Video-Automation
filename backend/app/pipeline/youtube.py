import threading
from pathlib import Path

from .. import config

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def is_connected() -> bool:
    return config.TOKEN_FILE.exists()


_state = {"connecting": False, "error": ""}


def state():
    return {"has_secret": config.CLIENT_SECRET.exists(), "connected": is_connected(), "connecting": _state["connecting"], "error": _state["error"]}


def start_connect():
    """Starts the Google sign-in in the background; a browser window opens on this PC."""
    if not config.CLIENT_SECRET.exists():
        raise RuntimeError("Upload your client_secret.json first.")
    if _state["connecting"]:
        return

    def run():
        _state.update(connecting=True, error="")
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file(str(config.CLIENT_SECRET), SCOPES)
            try:
                creds = flow.run_local_server(port=8090, prompt="consent", timeout_seconds=300)
            except TypeError:
                creds = flow.run_local_server(port=8090, prompt="consent")
            config.TOKEN_FILE.write_text(creds.to_json())
        except Exception as e:
            _state["error"] = ("Port 8090 is busy. Close other programs using it and try again." if "Address already in use" in str(e) or "10048" in str(e)
                               else str(e)[:300])
        finally:
            _state["connecting"] = False

    threading.Thread(target=run, daemon=True).start()


def disconnect():
    config.TOKEN_FILE.unlink(missing_ok=True)


def auth_cli():
    """Run once from the terminal: python -m backend.app.pipeline.youtube"""
    from google_auth_oauthlib.flow import InstalledAppFlow
    if not config.CLIENT_SECRET.exists():
        raise SystemExit("client_secret.json not found in the project root. See README step 6.")
    flow = InstalledAppFlow.from_client_secrets_file(str(config.CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(port=8090, prompt="consent")
    config.TOKEN_FILE.write_text(creds.to_json())
    print("YouTube connected. token.json saved.")


def _service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    if not config.TOKEN_FILE.exists():
        raise RuntimeError("YouTube is not connected. Run the one-time auth command from the README (step 6).")
    creds = Credentials.from_authorized_user_file(str(config.TOKEN_FILE), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        config.TOKEN_FILE.write_text(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def upload(video: Path, title, description, tags, privacy="private", thumbnail: Path = None, is_short=False):
    from googleapiclient.http import MediaFileUpload
    yt = _service()
    if is_short and "#shorts" not in description.lower():
        description = description.rstrip() + "\n\n#Shorts"
    body = {
        "snippet": {"title": title[:100], "description": description[:4900], "tags": tags[:30], "categoryId": "1"},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    media_body = MediaFileUpload(str(video), chunksize=8 * 1024 * 1024, resumable=True, mimetype="video/mp4")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media_body)
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    vid = resp["id"]
    thumb_error = ""
    if thumbnail and Path(thumbnail).exists():
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(thumbnail))).execute()
        except Exception as e:  # usually: channel not verified for custom thumbnails
            thumb_error = str(e)[:200]
    from .. import db
    db.add_usage("youtube_uploads", 1)
    return {"video_id": vid, "url": f"https://youtube.com/watch?v={vid}", "thumbnail_error": thumb_error}


if __name__ == "__main__":
    auth_cli()
