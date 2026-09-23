from fastapi import FastAPI, Query
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import pandas as pd
import json
import os
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API")
DATA_ROOT = Path(__file__).parent.parent / "data" / "youtube_corpus"
SNAPSHOT = Path(__file__).parent.parent / "data" / "dashboard_snapshot.json"

app = FastAPI(title="YouArgue API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CHANNELS = [
    {"id": "bbc_en",  "name": "BBC News",    "query": "BBC News",             "filter": ["BBC News"],                   "lang": "en", "color": "#ef4444"},
    {"id": "vrt_nl",  "name": "VRT NEWS",    "query": "VRT News",             "filter": ["VRT NEWS", "VRT NWS"],        "lang": "nl", "color": "#f97316"},
    {"id": "bbc_ru",  "name": "BBC Russian", "query": "BBC Русская служба",   "filter": ["BBC News - Русская служба"],  "lang": "ru", "color": "#3b82f6"},
    {"id": "zdf_de",  "name": "ZDFheute",    "query": "ZDFheute Nachrichten", "filter": ["ZDFheute Nachrichten"],       "lang": "de", "color": "#eab308"},
    {"id": "bfm_fr",  "name": "BFMTV",       "query": "BFMTV",                "filter": ["BFMTV"],                      "lang": "fr", "color": "#8b5cf6"},
]

CORPUS: dict = {}
_yt_cache: dict = {}
CACHE_TTL = 3600


def load_corpus():
    try:
        en1 = pd.read_csv(DATA_ROOT / "en_round1_clean.csv")
        en2 = pd.read_csv(DATA_ROOT / "en_round2_clean.csv")
        CORPUS["en"] = pd.concat([en1, en2], ignore_index=True)
        print(f"EN corpus loaded: {len(CORPUS['en'])} rows")
    except Exception as e:
        print(f"Could not load EN corpus: {e}")
    try:
        CORPUS["nl"] = pd.read_csv(DATA_ROOT / "dutch_round_clean.csv")
        print(f"NL corpus loaded: {len(CORPUS['nl'])} rows")
    except Exception as e:
        print(f"Could not load NL corpus: {e}")
    # German, French and Russian. Their annotation is model-produced rather than
    # human, so the app labels it as such -- but the file has the same shape as the
    # English and Dutch gold corpora, so every endpoint works unchanged.
    for lang in ("de", "fr", "ru"):
        try:
            CORPUS[lang] = pd.read_csv(DATA_ROOT / f"{lang}_ai_clean.csv")
            print(f"{lang.upper()} corpus loaded: {len(CORPUS[lang])} rows (AI-annotated)")
        except Exception as e:
            print(f"Could not load {lang.upper()} corpus: {e}")


# Which languages have human annotation, and which have model annotation. The app
# shows this on the corpus view so nobody mistakes one for the other.
ANNOTATION = {"en": "human", "nl": "human", "de": "ai", "fr": "ai", "ru": "ai"}


load_corpus()

# Model output, when it has been exported. Gold stays the default, so the app
# runs unchanged while data/predictions/ is empty.
import model_predictions as MP          # noqa: E402
import analysis_queue as AQ             # noqa: E402
MP.load_predictions()


def get_yt():
    if not YOUTUBE_API_KEY:
        return None
    try:
        from googleapiclient.discovery import build
        return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    except Exception as e:
        print(f"Could not build YouTube client: {e}")
        return None


def fetch_top_threads(video_id: str, yt, n: int = 5) -> list:
    try:
        resp = yt.commentThreads().list(
            videoId=video_id,
            part="snippet",
            order="relevance",
            maxResults=n,
            textFormat="plainText",
        ).execute()
        threads = []
        for item in resp.get("items", [])[:n]:
            snip = item["snippet"]["topLevelComment"]["snippet"]
            threads.append({
                "text": snip.get("textDisplay", "")[:200],
                "author": snip.get("authorDisplayName", "Anonymous"),
                "likes": int(snip.get("likeCount", 0)),
                "replies": int(item["snippet"].get("totalReplyCount", 0)),
            })
        return threads
    except Exception as e:
        print(f"Thread fetch error for {video_id}: {e}")
        return []



_snapshot_cache: dict | None = None


def _snapshot_videos(channel_id: str) -> list:
    """Videos for one channel from the committed snapshot, or [] if absent."""
    global _snapshot_cache
    if _snapshot_cache is None:
        try:
            _snapshot_cache = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Could not load dashboard snapshot ({SNAPSHOT}): {e}")
            _snapshot_cache = {}
    return _snapshot_cache.get("channels", {}).get(channel_id, [])


def fetch_channel_videos(ch: dict, start_date: str, end_date: str) -> list:
    cache_key = f"{ch['id']}_{start_date}_{end_date}"
    cached = _yt_cache.get(cache_key)
    if cached and time.time() - cached["ts"] < CACHE_TTL:
        return cached["data"]

    yt = get_yt()
    if not yt:
        # No API key: serve the committed snapshot so the dashboard works out of
        # the box. A reviewer who supplies a key gets live data instead.
        return _snapshot_videos(ch["id"])

    try:
        from googleapiclient.errors import HttpError

        search = yt.search().list(
            q=ch["query"],
            part="snippet",
            maxResults=50,
            order="viewCount",
            type="video",
            relevanceLanguage=ch["lang"],
            publishedAfter=start_date + "T00:00:00Z",
            publishedBefore=end_date + "T23:59:59Z",
        ).execute()

        ids = [
            i["id"]["videoId"]
            for i in search.get("items", [])
            if "videoId" in i.get("id", {})
        ]
        if not ids:
            # The live call succeeded but returned nothing for this window.
            snap = _snapshot_videos(ch["id"])
            if snap:
                print(f"No live results for {ch['id']} in {start_date}..{end_date}"
                      f" -- serving snapshot ({len(snap)} videos)")
            _yt_cache[cache_key] = {"ts": time.time(), "data": snap}
            return snap

        details = yt.videos().list(part="snippet,statistics", id=",".join(ids)).execute()

        videos = []
        for item in details.get("items", []):
            s = item["snippet"]
            st = item.get("statistics", {})
            if s.get("channelTitle") not in ch["filter"]:
                continue
            # A video with comments disabled reports no commentCount at all, and
            # asking for its threads returns 403. There is nothing to analyse on
            # one, so it is dropped here rather than failing later.
            if "commentCount" not in st or int(st["commentCount"]) < 1:
                continue
            threads = fetch_top_threads(item["id"], yt)
            videos.append({
                "video_id": item["id"],
                "title": s.get("title", ""),
                "published_at": s.get("publishedAt", ""),
                "channel_id": ch["id"],
                "channel_name": ch["name"],
                "channel_color": ch["color"],
                "thumbnail": s.get("thumbnails", {}).get("medium", {}).get("url", ""),
                "url": f"https://www.youtube.com/watch?v={item['id']}",
                "comment_count": int(st.get("commentCount", 0)),
                "view_count": int(st.get("viewCount", 0)),
                "like_count": int(st.get("likeCount", 0)),
                "threads": threads,
            })

        videos.sort(key=lambda x: x["comment_count"], reverse=True)
        _yt_cache[cache_key] = {"ts": time.time(), "data": videos}
        return videos

    except Exception as e:
        # Quota exhaustion, a network failure or a bad key all land here. Fall
        # back to the snapshot rather than showing an empty dashboard.
        print(f"YouTube error for {ch['id']}: {e} -- falling back to snapshot")
        return _snapshot_videos(ch["id"])


@app.get("/api/channels")
def get_channels():
    return CHANNELS


@app.get("/api/videos")
def get_videos(
    channel_id: Optional[str] = None,
    lang: Optional[str] = None,
    start_date: str = Query(...),
    end_date: str = Query(...),
):
    # Without a language filter this returned the top 20 by comment count across
    # every channel, and ZDFheute's volume meant French and Russian requests came
    # back full of German videos.
    targets = [c for c in CHANNELS
               if (not channel_id or c["id"] == channel_id)
               and (not lang or c["lang"] == lang)]

    # Comparing channels only means something against the other channels, so the
    # per-channel statistics are always computed over all of them. Only the video
    # list narrows to the selection. Results are cached per channel and window,
    # so the extra channels cost nothing after the first request.
    every = {ch["id"]: fetch_channel_videos(ch, start_date, end_date) for ch in CHANNELS}
    all_videos = [v for ch in targets for v in every[ch["id"]]]
    all_videos.sort(key=lambda x: x["comment_count"], reverse=True)

    channel_stats = {}
    for ch in CHANNELS:
        vids = every[ch["id"]]
        total_c = sum(v["comment_count"] for v in vids)
        total_v = sum(v["view_count"] for v in vids)
        total_l = sum(v["like_count"] for v in vids)
        channel_stats[ch["id"]] = {
            "id": ch["id"],
            "name": ch["name"],
            "color": ch["color"],
            "video_count": len(vids),
            "total_comments": total_c,
            "total_views": total_v,
            "total_likes": total_l,
            "avg_comments": total_c // len(vids) if vids else 0,
        }

    return {
        "videos": all_videos,
        "channel_stats": channel_stats,
        "total_videos": len(all_videos),
        "total_comments": sum(v["comment_count"] for v in all_videos),
        "total_views": sum(v["view_count"] for v in all_videos),
    }


# ── Corpus analysis ──────────────────────────────────────────────────────────

def _alias(lang: str) -> dict:
    return MP.topic_aliases(lang)


def _canon(cell: str, lang: str) -> list:
    """Topics in a gold cell, with surface-form aliases folded together."""
    a = _alias(lang)
    return [a.get(t.strip().lower(), t.strip().lower())
            for t in str(cell).split(",") if t.strip()]


def topic_in(cell: str, topic: str, lang: str = "") -> bool:
    return topic.lower() in _canon(cell, lang)


@app.get("/api/model/status")
def model_status():
    """Which languages have model predictions loaded, and from which models."""
    return {"languages": sorted(MP.PREDICTIONS.keys()), "detail": MP.MODEL_INFO,
            "gold_languages": sorted(CORPUS.keys())}


@app.post("/api/model/reload")
def model_reload():
    MP.load_predictions()
    return model_status()


class AnalysisRequest(BaseModel):
    video_id: str
    lang: str
    title: str = ""


@app.post("/api/analysis/request")
def request_analysis(req: AnalysisRequest):
    """Ask for a video to be analysed. Returns its current status."""
    analysed = any(v["title"] == req.title for v in MP.videos_with_predictions(req.lang)) \
        if req.title else False
    return AQ.request(req.video_id, req.lang, req.title, analysed=analysed)


@app.get("/api/analysis/queue")
def analysis_queue(lang: Optional[str] = None):
    """Every requested video and where it has got to."""
    q = AQ.all_requests()
    if lang:
        q = {k: v for k, v in q.items() if v.get("lang") == lang}
    return {"requests": list(q.values())}


@app.get("/api/analysis/videos")
def get_corpus_videos(lang: str, source: str = "gold"):
    if source == "model":
        done = MP.videos_with_predictions(lang)
        titles = {v["title"] for v in done}
        # Requested-but-not-yet-analysed videos appear too, marked, so a click on
        # "Add to analysis" has a visible effect instead of nothing until the run.
        pending = [{"title": r.get("title") or r["video_id"], "comment_count": 0,
                    "video_id": r["video_id"], "status": r.get("status", "queued")}
                   for r in AQ.all_requests().values()
                   if r.get("lang") == lang and r.get("status") in ("queued", "running")
                   and (r.get("title") or "") not in titles]
        for v in done:
            v["status"] = "done"
        return {"videos": done + pending, "lang": lang, "source": "model"}
    if lang not in CORPUS:
        return {"videos": [], "lang": lang}
    df = CORPUS[lang]
    has_annotator = "annotator" in df.columns
    agg = {"comment_count": ("comment_id", "nunique")}
    if has_annotator:
        agg["annotator_count"] = ("annotator", "nunique")
    grouped = (
        df.groupby("title")
        .agg(**agg)
        .reset_index()
        .sort_values("comment_count", ascending=False)
    )
    return {"videos": grouped.to_dict(orient="records"), "lang": lang}


@app.get("/api/analysis/topics")
def get_topics(title: str, lang: str, source: str = "gold", limit: int = 15):
    """source=gold shows your annotations; source=model shows model output."""
    if source == "model":
        return MP.topics_for_video(title, lang, limit=limit)
    if lang not in CORPUS:
        return {"topics": [], "title": title, "total_comments": 0, "thread_count": 0, "topic_count": 0}

    df = CORPUS[lang]
    vdf = df[df["title"] == title].copy()

    if vdf.empty:
        return {"topics": [], "title": title, "total_comments": 0, "thread_count": 0, "topic_count": 0}

    unique_comments = vdf.drop_duplicates(subset=["comment_id"])

    # Extract all unique topics
    all_topics: set = set()
    for col in ["stance_pro", "stance_con"]:
        for val in vdf[col].dropna():
            all_topics.update(_canon(val, lang))

    topic_list = []
    for topic in sorted(all_topics):
        pro_mask = unique_comments["stance_pro"].fillna("").apply(lambda x: topic_in(x, topic, lang))
        con_mask = unique_comments["stance_con"].fillna("").apply(lambda x: topic_in(x, topic, lang))

        # Strict: PRO means appears in stance_pro but NOT stance_con (and vice versa)
        pro_df = unique_comments[pro_mask & ~con_mask]
        con_df = unique_comments[con_mask & ~pro_mask]

        pro_count = len(pro_df)
        con_count = len(con_df)
        total = pro_count + con_count
        if total < 2:
            continue

        pro_pct = round(pro_count / total * 100)
        con_pct = 100 - pro_pct

        def fmt_comments(cdf, stance: str) -> list:
            CERTAINTY_WEIGHT = {"high": 1.5, "medium": 1.0, "low": 0.6}
            scored = []
            for _, r in cdf.iterrows():
                cid = r.get("comment_id", "")
                comment_rows = vdf[vdf["comment_id"] == cid]
                n = len(comment_rows)
                if n > 1:
                    votes = comment_rows["stance_pro" if stance == "pro" else "stance_con"].fillna("").apply(
                        lambda x: topic_in(x, topic, lang)
                    ).sum()
                    ratio = max(votes, n - votes) / n
                    confidence = "high" if ratio >= 0.8 else "medium" if ratio >= 0.6 else "low"
                else:
                    confidence = "medium"
                likes = int(r.get("like_count", 0))
                scored.append((likes * CERTAINTY_WEIGHT[confidence], confidence, r))

            # Highest certainty first, most-liked within a band -- same ordering
            # the model path uses, so the toggle compares like with like.
            order = {"high": 2, "medium": 1, "low": 0}
            scored.sort(key=lambda x: (order[x[1]], int(x[2].get("like_count", 0) or 0)),
                        reverse=True)
            result = []
            for _, confidence, r in scored[:limit]:
                result.append({
                    "comment_id": str(r.get("comment_id", "")),
                    "text": str(r.get("comment_text", "")),
                    "author": str(r.get("author", "Anonymous")),
                    "likes": int(r.get("like_count", 0)),
                    "date": str(r.get("published_date", ""))[:10],
                    "argument_type": str(r.get("argument_type", "")).split(",")[0].strip() if pd.notna(r.get("argument_type")) else "",
                    "confidence": confidence,
                })
            return result

        topic_list.append({
            "topic": topic,
            "pro_count": pro_count,
            "con_count": con_count,
            "total": total,
            "pro_pct": pro_pct,
            "con_pct": con_pct,
            "pro_comments": fmt_comments(pro_df, "pro"),
            "con_comments": fmt_comments(con_df, "con"),
        })

    topic_list.sort(key=lambda x: x["total"], reverse=True)

    thread_count = 0
    if "root_comment_id" in unique_comments.columns:
        thread_count = int(unique_comments["root_comment_id"].nunique())

    return {
        "title": title,
        "lang": lang,
        "total_comments": len(unique_comments),
        "thread_count": thread_count,
        "topic_count": len(topic_list),
        "topics": topic_list,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
