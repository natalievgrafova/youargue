"""Freeze one dashboard window so the demo works without an API key.

Run once with a key in .env; commit data/dashboard_snapshot.json. The backend
falls back to it whenever YOUTUBE_API is unset.
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
import main as B  # noqa: E402

START, END = sys.argv[1], sys.argv[2]

if not B.YOUTUBE_API_KEY:
    sys.exit("No YOUTUBE_API in .env -- this script needs a key to build the snapshot.")

out = {"start_date": START, "end_date": END, "channels": {}}
for ch in B.CHANNELS:
    vids = B.fetch_channel_videos(ch, START, END)
    out["channels"][ch["id"]] = vids
    print(f"  {ch['name']:<14} {len(vids):>3} videos")

B.SNAPSHOT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
print(f"\nwrote {B.SNAPSHOT}  ({B.SNAPSHOT.stat().st_size/1e6:.1f} MB)")
