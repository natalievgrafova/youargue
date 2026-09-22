"""Collect recent videos from the app's channels and prepare them for analysis.

    python3 tools/batch_analyse.py --lang en --videos 3 --dry-run
    python3 tools/batch_analyse.py --lang en --videos 3

Videos are ranked by how close they sit to the topic pool -- argument mining
only pays off on contested videos, and this skips sport, weather and celebrity
items before any GPU time is spent. All selected videos for a language go into
ONE pair file, so the language costs one model load rather than one per video.
"""
import argparse, subprocess, sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyse_video import (CHANNELS, ADAPTERS, POOL, REMOTE,
                           fetch_comments, narrow)                                    # noqa: E402

def app_channels():
    """The app's own channel config, read from backend/main.py.

    The backend already resolves a channel by exact `channelTitle` membership in
    its `filter` list -- 'BBC News' must not match 'BBC News 中文'. Read that
    config rather than keeping a second copy that can drift from it.
    """
    import ast
    src = (Path(__file__).resolve().parent.parent / "backend" / "main.py").read_text(encoding="utf-8")
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "CHANNELS":
            return {c["lang"]: c for c in ast.literal_eval(node.value)}
    raise SystemExit("CHANNELS not found in backend/main.py")


CHANNEL = app_channels()
QUERY = {lang: (c["query"], c["filter"]) for lang, c in CHANNEL.items()}


def candidates(lang, since, until, min_comments):
    import os
    from dotenv import load_dotenv
    from googleapiclient.discovery import build
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    yt = build("youtube", "v3", developerKey=os.getenv("YOUTUBE_API"))
    ch = CHANNEL[lang]
    keep = ch["filter"]
    ids = []
    for order in ("relevance", "viewCount"):     # same call the backend makes, both orderings
        r = yt.search().list(part="snippet", q=ch["query"], type="video", order=order,
                             relevanceLanguage=ch["lang"], maxResults=50,
                             publishedAfter=f"{since}T00:00:00Z",
                             publishedBefore=f"{until}T23:59:59Z").execute()
        ids += [i["id"]["videoId"] for i in r.get("items", []) if "videoId" in i.get("id", {})]
    out = []
    for i in range(0, len(set(ids)), 50):
        chunk = list(set(ids))[i:i + 50]
        for v in yt.videos().list(part="snippet,statistics", id=",".join(chunk)).execute()["items"]:
            s, st = v["snippet"], v["statistics"]
            # exact title: "BBC News" is a prefix of "BBC News 中文", "BBC News हिंदी" etc.,
            # and those are different channels in different languages.
            if s.get("channelTitle") not in keep:      # exactly the backend's test
                continue
            n = int(st.get("commentCount", 0))
            if n < min_comments:
                continue
            out.append({"video_id": v["id"], "title": s["title"], "comments": n,
                        "published": s["publishedAt"][:10],
                        "text": s["title"] + ". " + s["description"][:400]})
    return pd.DataFrame(out).drop_duplicates(subset=["video_id"])


def rank_by_pool(df, lang):
    """How contested does this video look, judged by the curated inventory?

    Was: embedding distance to the Wikipedia topic pool. That ranked a video by
    vague thematic resemblance, which is the same weakness that made the pool
    useless for candidate generation. Here the score is the number of curated
    targets whose surface forms actually occur in the title and description --
    the same test the pipeline applies later, so the ranking and the shortlist
    agree with each other.
    """
    sys.path.insert(0, str(POOL / "curated"))
    from mentions import load_aliases, hit
    csv = POOL / "curated" / "curated_topics_checked.csv"
    aliases = load_aliases(lang, str(csv))
    targets = pd.read_csv(csv)["target"].tolist()
    scores, nearest = [], []
    for text in df["text"].tolist():
        found = []
        for t in targets:
            for a in aliases.get(t.lower(), [t]):
                if hit(text, a, lang)[0]:
                    found.append(t); break
        scores.append(len(found))
        nearest.append(", ".join(found[:3]))
    df = df.copy()
    df["pool_score"] = scores
    df["nearest"] = nearest
    return df.sort_values(["pool_score", "comments"], ascending=False)


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--lang", default="en", choices=list(QUERY))
    a.add_argument("--videos", type=int, default=3)
    a.add_argument("--since", default="2026-08-01")
    a.add_argument("--until", default="2026-09-01", help="the app's date range, end")
    a.add_argument("--min-comments", type=int, default=200)
    a.add_argument("--comments-per-video", type=int, default=100)
    a.add_argument("--threads", type=int, default=5, help="busiest threads per video")
    a.add_argument("--topics", type=int, default=15, help="from the Wikipedia pool")
    a.add_argument("--yake", type=int, default=10, help="seeds from the comments; 0 disables")
    a.add_argument("--dry-run", action="store_true")
    args = a.parse_args()

    cand = candidates(args.lang, args.since, args.until, args.min_comments)
    if cand.empty:
        sys.exit("no candidate videos -- widen --since or lower --min-comments")
    ranked = rank_by_pool(cand, args.lang)
    print(f"{len(ranked)} candidates from {CHANNEL[args.lang]['name']} "
          f"({args.since} to {args.until}):\n")
    for _, r in ranked.head(10).iterrows():
        print(f"  {r.pool_score:.3f} | {r.comments:>5} comments | {r.published} | {r.title[:58]}")
        print(f"          nearest pool topics: {r.nearest}")
    picked = ranked.head(args.videos)
    print(f"\nselected {len(picked)}: " + ", ".join(picked.video_id))
    if args.dry_run:
        return

    from analyse_video import shortlist
    frames, manifest = [], []
    for _, v in picked.iterrows():
        lang, title, df, survey = fetch_comments(v.video_id, args.comments_per_video, args.threads)
        topics, _ = shortlist(survey, lang, args.topics, args.yake)
        frames.append(pd.DataFrame([{**r, "topic": t.lower(), "label": 0, "stance": "con", "gold_stance": ""}
                                    for _, r in df.iterrows() for t in topics]))
        manifest.append({"video_id": v.video_id, "title": title, "comments": len(df), "threads": int(df.root_comment_id.nunique()),
                         "topics": "; ".join(topics)})
        print(f"  {title[:55]}: {len(df)} comments x {len(topics)} topics")
    pairs = pd.concat(frames, ignore_index=True)
    name = f"batch_{args.lang}"
    local = POOL / f"{name}_pairs.csv"
    pairs.to_csv(local, index=False)
    pd.DataFrame(manifest).to_csv(POOL / f"{name}_manifest.csv", index=False)
    print(f"\n{len(pairs)} pairs across {len(picked)} videos -> {local.name}")
    subprocess.run(["scp", "-q", str(local), f"hpc:{REMOTE}/data/app_input/"], check=True)

    tm, ta, tc, sm, sa, sc = ADAPTERS[args.lang]
    ck = "/kyukon/scratch/gent/vo/000/gvo00042/vsc47819/demo_paper/checkpoints"
    script = f"""cd {REMOTE}
T=$(qsub -N {name}_topic -l walltime=10:00:00 -v "RUN_TAG={name}_topic,LANG={args.lang},TASK=binary,MODEL_NAME={tm},ADAPTER_PATH={ck}/{ta}/best_adapter,CONTEXT={tc},SHOTS=0,TEST_NAME=app_pairs,TEST_PATH=data/app_input/{local.name}" scripts/pbs/eval_human.pbs)
echo "topic  $T"
S=$(qsub -N {name}_stance -W depend=afterok:$T -v "RUN_TAG={name}_stance,LANG={args.lang},MODEL_NAME={sm},ADAPTER_PATH={ck}/{sa}/best_adapter,CONTEXT={sc},TOPIC_RUN={name}_topic,TOPIC_CONTEXT={tc}" scripts/pbs/app_stance.pbs)
echo "stance $S (after $T)"
"""
    subprocess.run(["ssh", "hpc", "bash -lc 'module swap cluster/accelgor >/dev/null 2>&1; bash -s'"],
                   input=script, text=True, check=True)


if __name__ == "__main__":
    main()
