import queue
import threading

from . import config, db
from .pipeline.runner import run_job

_q: "queue.Queue[str]" = queue.Queue()


def _loop():
    while True:
        job_id = _q.get()
        try:
            run_job(job_id)
        finally:
            _q.task_done()


def start():
    for _ in range(max(1, config.WORKER_THREADS)):
        threading.Thread(target=_loop, daemon=True).start()
    # resume anything interrupted by a restart
    for j in db.jobs_with_status("queued", "running"):
        db.update_job(j["id"], status="queued", stage="Waiting in queue", progress=0)
        _q.put(j["id"])


def enqueue(job_id):
    _q.put(job_id)
