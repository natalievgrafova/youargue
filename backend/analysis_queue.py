"""Videos requested for analysis from the dashboard.

The models run on a GPU elsewhere, so the button cannot analyse a video on the
spot. It records a request; an operator (or a cron) runs tools/run_queue.py,
which does the fetch, shortlist and submission and writes the status back. The
Analysis page reads this file so a requested video appears immediately, marked
as pending, instead of silently missing until the run finishes.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

QUEUE = Path(__file__).parent.parent / "data" / "predictions" / "analysis_queue.json"
STATUSES = ("queued", "running", "done", "failed")


def _read() -> dict:
    try:
        return json.loads(QUEUE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write(d: dict) -> None:
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    QUEUE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def all_requests() -> dict:
    return _read()


def status_for(video_id: str) -> dict | None:
    return _read().get(video_id)


def request(video_id: str, lang: str, title: str = "", analysed: bool = False) -> dict:
    """Record a request. Already-analysed videos are reported, not re-queued."""
    q = _read()
    if analysed:
        return {"video_id": video_id, "status": "done", "note": "already analysed"}
    cur = q.get(video_id)
    if cur and cur.get("status") in ("queued", "running"):
        return cur                      # idempotent: clicking twice changes nothing
    q[video_id] = {"video_id": video_id, "lang": lang, "title": title,
                   "status": "queued",
                   "requested_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    _write(q)
    return q[video_id]


def set_status(video_id: str, status: str, note: str = "") -> None:
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}")
    q = _read()
    entry = q.setdefault(video_id, {"video_id": video_id})
    entry.update(status=status, note=note,
                 updated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    _write(q)
