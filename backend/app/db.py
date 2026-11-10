import json
import sqlite3
import threading
import time
import uuid

from .config import DB_PATH

_lock = threading.Lock()
_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
_conn.row_factory = sqlite3.Row

JSON_FIELDS = ("input", "result")


def init():
    with _lock:
        _conn.execute(
            """CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                stage TEXT DEFAULT '',
                progress INTEGER DEFAULT 0,
                input TEXT DEFAULT '{}',
                result TEXT DEFAULT '{}',
                error TEXT DEFAULT '',
                created REAL,
                updated REAL
            )"""
        )
        _conn.execute(
            """CREATE TABLE IF NOT EXISTS used_movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                year INTEGER,
                job_id TEXT DEFAULT '',
                created REAL
            )"""
        )
        _conn.execute(
            """CREATE TABLE IF NOT EXISTS usage (
                day TEXT NOT NULL, service TEXT NOT NULL, amount INTEGER DEFAULT 0,
                PRIMARY KEY (day, service)
            )"""
        )
        _conn.commit()


def _row(r):
    if r is None:
        return None
    d = dict(r)
    for f in JSON_FIELDS:
        d[f] = json.loads(d[f] or "{}")
    return d


def create_job(inp: dict) -> str:
    job_id = uuid.uuid4().hex[:10]
    now = time.time()
    with _lock:
        _conn.execute(
            "INSERT INTO jobs (id,status,stage,progress,input,result,created,updated) VALUES (?,?,?,?,?,?,?,?)",
            (job_id, "queued", "Waiting in queue", 0, json.dumps(inp), "{}", now, now),
        )
        _conn.commit()
    return job_id


def get_job(job_id):
    with _lock:
        r = _conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    return _row(r)


def list_jobs(limit=50):
    with _lock:
        rows = _conn.execute("SELECT * FROM jobs ORDER BY created DESC LIMIT ?", (limit,)).fetchall()
    return [_row(r) for r in rows]


def update_job(job_id, **fields):
    if not fields:
        return
    for f in JSON_FIELDS:
        if f in fields:
            fields[f] = json.dumps(fields[f])
    fields["updated"] = time.time()
    cols = ", ".join(f"{k}=?" for k in fields)
    with _lock:
        _conn.execute(f"UPDATE jobs SET {cols} WHERE id=?", (*fields.values(), job_id))
        _conn.commit()


def jobs_with_status(*statuses):
    q = ",".join("?" * len(statuses))
    with _lock:
        rows = _conn.execute(f"SELECT * FROM jobs WHERE status IN ({q}) ORDER BY created", statuses).fetchall()
    return [_row(r) for r in rows]


# ---- movies already covered (kept so videos never repeat a film) ----
def used_movies():
    with _lock:
        rows = _conn.execute("SELECT id,title,year,job_id FROM used_movies ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def add_used_movies(movies, job_id=""):
    with _lock:
        for m in movies:
            _conn.execute("INSERT INTO used_movies (title,year,job_id,created) VALUES (?,?,?,?)",
                          (m["title"], m.get("year"), job_id, time.time()))
        _conn.commit()


def delete_used_movie(movie_id):
    with _lock:
        _conn.execute("DELETE FROM used_movies WHERE id=?", (movie_id,))
        _conn.commit()


def delete_used_for_job(job_id):
    with _lock:
        _conn.execute("DELETE FROM used_movies WHERE job_id=?", (job_id,))
        _conn.commit()


# ---- daily usage counters (day follows Google's quota reset: midnight Pacific time) ----
def today():
    from datetime import datetime, timedelta, timezone
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d")
    except Exception:  # Windows without the tz database: fixed offset (off by an hour during summer time)
        return datetime.now(timezone(timedelta(hours=-8))).strftime("%Y-%m-%d")


def add_usage(service, amount=1):
    try:
        with _lock:
            _conn.execute("INSERT INTO usage (day,service,amount) VALUES (?,?,?) "
                          "ON CONFLICT(day,service) DO UPDATE SET amount = amount + ?",
                          (today(), service, amount, amount))
            _conn.commit()
    except Exception:
        pass  # counting must never break a video


def get_usage(service, day=None):
    with _lock:
        r = _conn.execute("SELECT amount FROM usage WHERE day=? AND service=?", (day or today(), service)).fetchone()
    return int(r["amount"]) if r else 0


def delete_job(job_id):
    with _lock:
        _conn.execute("DELETE FROM jobs WHERE id=?", (job_id,))
        _conn.commit()


def total_ai_requests():
    """All AI requests this app made today (every provider)."""
    with _lock:
        r = _conn.execute("SELECT COALESCE(SUM(amount),0) AS n FROM usage WHERE day=? AND service LIKE '%\\_requests' ESCAPE '\\'",
                          (today(),)).fetchone()
    return int(r["n"])
