"""Analyse the videos requested from the dashboard.

The button records a request; this does the work. Run it manually, or on a cron:

    python3 tools/run_queue.py            # analyse everything queued
    python3 tools/run_queue.py --dry-run  # just list what is waiting

Each video goes through the same path as tools/analyse_video.py -- fetch, topic
shortlist, pairs, submit -- and its status is written back so the Analysis page
shows queued, running, done or failed.
"""
import argparse, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
import analysis_queue as AQ  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--topics", type=int, default=15)
    ap.add_argument("--yake", type=int, default=10)
    a = ap.parse_args()

    waiting = [r for r in AQ.all_requests().values() if r.get("status") == "queued"]
    if not waiting:
        print("nothing queued")
        return
    print(f"{len(waiting)} video(s) queued:")
    for r in waiting:
        print(f"  {r['lang']}  {r['video_id']}  {r.get('title','')[:56]}")
    if a.dry_run:
        return

    for r in waiting:
        AQ.set_status(r["video_id"], "running")
        cmd = [sys.executable, str(ROOT / "tools" / "analyse_video.py"), r["video_id"],
               "--topics", str(a.topics), "--yake", str(a.yake)]
        print(f"\n=== {r['video_id']} ===")
        rc = subprocess.run(cmd, cwd=ROOT).returncode
        if rc == 0:
            # submitted to the cluster; predictions arrive via fetch_predictions.sh
            AQ.set_status(r["video_id"], "running", "submitted to the cluster")
            print("  submitted - run tools/fetch_predictions.sh when the jobs finish")
        else:
            AQ.set_status(r["video_id"], "failed", f"analyse_video exited {rc}")
            print(f"  FAILED (exit {rc})")


if __name__ == "__main__":
    main()
