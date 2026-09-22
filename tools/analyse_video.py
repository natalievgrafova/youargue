"""Prepare a new video for model analysis.

    python3 tools/analyse_video.py <video_id> [--topics 25] [--max-comments 800]

Fetches the comments, shortlists the curated targets whose aliases actually
appear in the video, writes the (comment, topic) pairs
and uploads them, then submits the two chained HPC jobs. Results reach the app
through tools/fetch_predictions.sh like every other prediction.

Only the four channels the app is configured for are accepted -- the pipeline
that decides *which* videos exist is unchanged; this only analyses one of them.
"""
import argparse, os, subprocess, sys
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
POOL = ROOT / "topic_pool"          # bundled, so a clone is self-contained
REMOTE = "/data/gent/vo/000/gvo00042/vsc47819/demo_paper"
CHANNELS = {                       # the app's configured channels, by channel title
    "BBC News": "en", "VRT NEWS": "nl", "VRT NWS": "nl",
    "BBC News - Русская служба": "ru", "ZDFheute Nachrichten": "de",
    "BFMTV": "fr",                 # the channel the French annotated corpus came from
}
ADAPTERS = {                       # (topic model, topic adapter, topic context,
                                   #  stance model, stance adapter, stance context)
    # English relevance was seqllm_llama_en_binary (Llama-3.1-8B, title) until it was
    # compared within its own evaluation condition: 0.611 macro-F1 against 0.737 for
    # this Gemma adapter on the same split, same approach.
    "en": ("google/gemma-2-9b-it", "ctx4_gemma_en_topic_none", "none",
           "google/gemma-2-9b-it", "ctx4_gemma_en_root", "root"),
    "nl": ("google/gemma-2-9b-it", "ctx4_gemma_nl_topic_description", "description",
           "google/gemma-2-9b-it", "seqllm_gemma_nl_stance", "title"),
    # German, French and Russian run the silver models: Gemma-2-9B LoRA trained on the
    # model-annotated splits and tested against human-verified sets. Contexts are the
    # ones each adapter was trained with -- title for relevance, root for stance.
    "de": ("google/gemma-2-9b-it", "sv_gemma_de_binary", "title",
           "google/gemma-2-9b-it", "sv_gemma_de_stance", "root"),
    "fr": ("google/gemma-2-9b-it", "sv_gemma_fr_binary", "title",
           "google/gemma-2-9b-it", "sv_gemma_fr_stance", "root"),
    "ru": ("google/gemma-2-9b-it", "sv_gemma_ru_binary", "title",
           "google/gemma-2-9b-it", "sv_gemma_ru_stance", "root"),
}


def fetch_comments(video_id, limit, max_threads=5):
    """The busiest threads of a video, whole rather than sampled.

    A thread is where the argument happens: the root claim plus everyone
    answering it. Taking the `max_threads` most-replied threads in full gives the
    stance model its `root` context, which loose top-level comments would not.
    """
    load_dotenv(ROOT / ".env")
    from googleapiclient.discovery import build
    yt = build("youtube", "v3", developerKey=os.getenv("YOUTUBE_API"))
    v = yt.videos().list(part="snippet", id=video_id).execute()["items"]
    if not v:
        sys.exit(f"video {video_id} not found")
    snip = v[0]["snippet"]
    channel = snip["channelTitle"]
    if channel not in CHANNELS:
        sys.exit(f"'{channel}' is not one of the app's channels: {sorted(set(CHANNELS))}")

    threads, token = [], None
    for _ in range(5):                                  # up to 500 threads to rank
        r = yt.commentThreads().list(part="snippet", videoId=video_id, maxResults=100,
                                     order="relevance", textFormat="plainText",
                                     pageToken=token).execute()
        for it in r["items"]:
            threads.append((it["snippet"].get("totalReplyCount", 0), it))
        token = r.get("nextPageToken")
        if not token:
            break
    # Every thread's top-level comment, kept as a broad view of what the video is
    # about. The busiest threads alone are a biased sample: on one video the five
    # largest arguments were about Europe while the video was about virus design.
    survey = [it["snippet"]["topLevelComment"]["snippet"]["textDisplay"] for _, it in threads]
    threads.sort(key=lambda t: t[0], reverse=True)

    rows = []
    for n_replies, it in threads[:max_threads]:
        top = it["snippet"]["topLevelComment"]; s = top["snippet"]
        rows.append(dict(comment_id=top["id"], root_comment_id=top["id"], is_root=True,
                         comment_text=s["textDisplay"], author=s["authorDisplayName"],
                         like_count=s.get("likeCount", 0), published_date=s["publishedAt"][:10],
                         root_comment_text=""))
        rtok = None
        while n_replies and len(rows) < limit:           # replies in full, not the inline 5
            rr = yt.comments().list(part="snippet", parentId=top["id"], maxResults=100,
                                    textFormat="plainText", pageToken=rtok).execute()
            for rep in rr["items"]:
                rs = rep["snippet"]
                rows.append(dict(comment_id=rep["id"], root_comment_id=top["id"], is_root=False,
                                 comment_text=rs["textDisplay"], author=rs["authorDisplayName"],
                                 like_count=rs.get("likeCount", 0),
                                 published_date=rs["publishedAt"][:10],
                                 root_comment_text=s["textDisplay"]))
            rtok = rr.get("nextPageToken")
            if not rtok:
                break
        if len(rows) >= limit:
            break
    rows = rows[:limit]
    for r in rows:
        r.update(title=snip["title"], video_description=snip["description"][:1500], video_id=video_id)
    link_parents(rows)
    return CHANNELS[channel], snip["title"], pd.DataFrame(rows), survey


def link_parents(rows):
    """Which comment is this a reply to.

    The API gives every reply the same parentId -- the thread root -- so replies
    inside a thread are flat and their order is not their structure. The real
    link is in the text: YouTube opens a reply with the parent author's handle.
    A reply with no handle is a direct reply to the top comment.

    Resolved here, while the handles are still present: de-identification runs
    later and replaces them with @user.
    """
    import re
    by_author = {}
    for r in rows:
        by_author.setdefault(str(r["author"]).lstrip("@").lower(), r["comment_id"])
    for r in rows:
        r["parent_comment_id"] = ""
        r["parent_comment_text"] = ""
        if r["is_root"]:
            continue
        m = re.match(r"\s*@+([\w.\-]{2,})", str(r["comment_text"]))
        if not m:                                   # no handle: reply to the root
            r["parent_comment_id"] = r["root_comment_id"]
            r["parent_comment_text"] = r["root_comment_text"]
            continue
        h = m.group(1).lower()
        for L in range(len(h), 3, -1):              # the handle may run into the next word
            pid = by_author.get(h[:L])
            if pid and pid != r["comment_id"]:
                r["parent_comment_id"] = pid
                break
    text = {r["comment_id"]: r["comment_text"] for r in rows}
    for r in rows:
        if r["parent_comment_id"] and not r["parent_comment_text"]:
            r["parent_comment_text"] = text.get(r["parent_comment_id"], "")


def narrow(df, max_threads, limit):
    """The scored subset: the first `max_threads` threads, capped at `limit`."""
    keep = list(dict.fromkeys(df["root_comment_id"]))[:max_threads]
    return df[df["root_comment_id"].isin(keep)].head(limit).reset_index(drop=True)


def shortlist(df, lang, k=None, yake_k=None):
    """Candidate topics for this video: the curated targets whose aliases appear in it.

    Was: rank the Wikipedia contested-issues pool by embedding distance, plus YAKE
    seeds. That produced candidates the video never mentions -- `united nations`
    scored on a video where neither "UN" nor "United Nations" occurs -- and the
    relevance model then had to reject them one comment at a time.

    Now: a target is a candidate only if one of its aliases is actually in the
    text. `k` and `yake_k` are ignored; the video decides how many candidates it
    has. On the English China video that is 27 of 246 targets.
    """
    sys.path.insert(0, str(POOL / "curated"))
    from mentions import load_aliases, hit
    csv = POOL / "curated" / "curated_topics_checked.csv"
    aliases = load_aliases(lang, str(csv))
    targets = pd.read_csv(csv)["target"].tolist()

    if isinstance(df, list):
        blob = " \n ".join(str(t) for t in df)
    else:
        parts = [str(df["title"].iloc[0]), str(df.get("video_description", pd.Series([""])).iloc[0])]
        parts += df["comment_text"].dropna().astype(str).tolist()
        if "root_comment_text" in df.columns:
            parts += df["root_comment_text"].dropna().astype(str).tolist()
        blob = " \n ".join(parts)

    chosen, why = [], {}
    for t in targets:
        for a in aliases.get(t.lower(), [t]):
            ok, evidence, how = hit(blob, a, lang)
            if ok:
                chosen.append(t); why[t] = (a, evidence, how); break
    for t in chosen:
        a, e, how = why[t]
        print(f"    {t:34} <- {e!r} ({how}, alias {a!r})")
    return chosen, csv.name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id")
    ap.add_argument("--topics", type=int, default=None, help="ignored: the alias match decides")
    ap.add_argument("--yake", type=int, default=None, help="ignored: kept so old commands still run")
    ap.add_argument("--max-comments", type=int, default=100)
    ap.add_argument("--threads", type=int, default=5, help="busiest threads per video")
    ap.add_argument("--dry-run", action="store_true", help="stop after the shortlist")
    a = ap.parse_args()

    # Keyword extraction is free and scoring is not, so read widely for the
    # shortlist and score narrowly: seeds drawn from only the 5 scored threads
    # describe those threads, not the video.
    lang, title, df, survey = fetch_comments(a.video_id, a.max_comments, a.threads)
    print(f"{title}\n  {lang} | {len(df)} comments scored, {len(survey)} surveyed for topics")
    print(f"  matching the curated list against the video:")
    topics, pool_name = shortlist(survey, lang)
    print(f"  {pool_name} -> {len(topics)} candidates")
    if not topics:
        sys.exit("  no curated target is named in this video")
    if a.dry_run:
        return
    if lang not in ADAPTERS:
        sys.exit(f"no trained topic/stance models for '{lang}' yet -- shortlist only")

    pairs = pd.DataFrame([{**r, "topic": t.lower(), "label": 0, "stance": "con", "gold_stance": ""}
                          for _, r in df.iterrows() for t in topics])
    name = f"nv_{a.video_id}"
    local = POOL / f"{name}_pairs.csv"
    pairs.to_csv(local, index=False)
    print(f"  {len(pairs)} pairs -> {local.name}")
    subprocess.run(["scp", "-q", str(local), f"hpc:{REMOTE}/data/app_input/"], check=True)

    tm, ta, tc, sm, sa, sc = ADAPTERS[lang]
    ck = "/kyukon/scratch/gent/vo/000/gvo00042/vsc47819/demo_paper/checkpoints"
    script = f"""cd {REMOTE}
T=$(qsub -N {name}_topic -l walltime=08:00:00 -v "RUN_TAG={name}_topic,LANG={lang},TASK=binary,MODEL_NAME={tm},ADAPTER_PATH={ck}/{ta}/best_adapter,CONTEXT={tc},SHOTS=0,TEST_NAME=app_pairs,TEST_PATH=data/app_input/{local.name}" scripts/pbs/eval_human.pbs)
echo "topic  $T"
S=$(qsub -N {name}_stance -W depend=afterok:$T -v "RUN_TAG={name}_stance,LANG={lang},MODEL_NAME={sm},ADAPTER_PATH={ck}/{sa}/best_adapter,CONTEXT={sc},TOPIC_RUN={name}_topic,TOPIC_CONTEXT={tc}" scripts/pbs/app_stance.pbs)
echo "stance $S (after $T)"
"""
    subprocess.run(["ssh", "hpc", "bash -lc 'module swap cluster/accelgor >/dev/null 2>&1; bash -s'"],
                   input=script, text=True, check=True)
    print("  submitted. When both finish: bash tools/fetch_predictions.sh")


if __name__ == "__main__":
    main()
