"""Merge the HPC topic + stance predictions into the file the app reads.

    python3 tools/merge_predictions.py en
    python3 tools/merge_predictions.py nl

Writes data/predictions/<lang>_app_predictions.csv.
"""
import json, math, os, sys
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POOL = ROOT.parent / "demo_YouArgue" / "topic_pool"
# The topic model fires far more often than the gold base rate (61% vs 27% EN),
# so argmax relevance floods the app with false topics. Score-threshold instead;
# None keeps the model's own decision.
THRESHOLD = float(os.environ["RELEVANCE_THRESHOLD"]) if os.environ.get("RELEVANCE_THRESHOLD") else None
# NL's relevance scores are compressed -- nothing clears 0.90, where EN reaches
# 0.999 -- so an absolute cutoff silently empties the Dutch app. A percentile
# keeps the same *share* of pairs in both languages.
TOP_PCT = float(os.environ["RELEVANCE_TOP_PCT"]) if os.environ.get("RELEVANCE_TOP_PCT") else None


def relevance_from_logits(topic: pd.DataFrame) -> pd.Series | None:
    """P(relevant) from the per-class logits the eval run stored.

    `p_pro` is written by whichever code path produced the file and has been
    a constant 0.5 in older runs; `raw_output` carries the logits themselves,
    so derive from that and treat p_pro only as a fallback.
    """
    if "raw_output" not in topic.columns:
        return None
    def one(v):
        try:
            d = json.loads(v)
            neg, pos = float(d["0"]), float(d["1"])
        except Exception:
            return None
        return 1.0 / (1.0 + math.exp(min(60.0, max(-60.0, neg - pos))))
    p = topic["raw_output"].map(one)
    return p if p.notna().mean() > 0.99 else None
RAW = ROOT / "data" / "predictions" / "raw"
MODELS = {"en": ("ctx4_gemma_en_topic_none (Gemma-2-9B, no context)",
                 "ctx4_gemma_en_root (Gemma-2-9B, root)"),
          "nl": ("ctx4_gemma_nl_topic_description (Gemma-2-9B, description)",
                 "seqllm_gemma_nl_stance (Gemma-2-9B, title)"),
          # silver models: trained on the model-annotated splits, tested on human-verified sets
          "de": ("sv_gemma_de_binary (Gemma-2-9B, title)", "sv_gemma_de_stance (Gemma-2-9B, root)"),
          "fr": ("sv_gemma_fr_binary (Gemma-2-9B, title)", "sv_gemma_fr_stance (Gemma-2-9B, root)"),
          "ru": ("sv_gemma_ru_binary (Gemma-2-9B, title)", "sv_gemma_ru_stance (Gemma-2-9B, root)")}

def main(lang: str) -> None:
    # An unseen video, if it has been run, is appended to the same language file
    # so it appears in the app beside the annotated ones; `source` tells them apart.
    # Which runs belong to the current pipeline is a property of the data, not of
    # the file name: pairs built by the curated shortlist carry the parent comment
    # through, because the grounding rule needs it. Legacy runs from the Wikipedia
    # topic pool do not, and mixing them in both floods the app with targets the
    # inventory no longer contains and makes the grounding rule drop nearly
    # everything. Set YOUARGUE_ALL_RUNS=1 to merge the legacy runs back in.
    def carries_parent(f):
        if not f.exists():
            return False
        return "parent_comment_text" in pd.read_csv(f, nrows=1).columns

    every = [(RAW / f"{lang}_topic_predictions.csv", RAW / f"{lang}_stance_predictions.csv")]
    for kind in ("batch", "newvideo", "curated"):
        every.append((RAW / f"{lang}_{kind}_topic_predictions.csv",
                      RAW / f"{lang}_{kind}_stance_predictions.csv"))
    every = [p for p in every if all(x.exists() for x in p)]
    parts = [p for p in every if carries_parent(p[0])]
    if not parts or os.environ.get("YOUARGUE_ALL_RUNS"):
        parts = every
        print("  including every run found, legacy pools among them")
    else:
        skipped = len(every) - len(parts)
        print(f"  {len(parts)} curated run(s): " + ", ".join(p[0].name for p in parts)
              + (f"   ({skipped} legacy run(s) skipped)" if skipped else ""))

    topic = pd.concat([pd.read_csv(t) for t, _ in parts if t.exists()], ignore_index=True)
    sys.path.insert(0, str(POOL / "curated"))
    from dedup import dedup_pairs
    n0 = len(topic); topic = dedup_pairs(topic)
    if len(topic) != n0:
        print(f"  dropped {n0 - len(topic)} pairs repeating a comment already scored")
    stance = pd.concat([pd.read_csv(s) for _, s in parts if s.exists()], ignore_index=True)
    key = ["comment_id", "topic"]

    # Both files carry a `confidence` column; without renaming, the merge
    # suffixes them and the app ends up with neither.
    topic = topic.rename(columns={"confidence": "topic_confidence", "p_pro": "relevance_score"})
    derived = relevance_from_logits(topic)
    if derived is not None:
        old = pd.to_numeric(topic.get("relevance_score"), errors="coerce")
        if old is None or old.nunique(dropna=True) <= 1:
            print(f"  relevance_score recovered from raw_output "
                  f"({derived.nunique()} distinct; the stored column had "
                  f"{0 if old is None else old.nunique(dropna=True)})")
        topic["relevance_score"] = derived
    topic["relevant"] = topic["prediction"].astype(str).str.strip().isin(("1", "1.0", "relevant")).astype(int)

    score = pd.to_numeric(topic.get("relevance_score"), errors="coerce")
    if score is not None and score.nunique(dropna=True) > 1:
        cut = None
        if TOP_PCT is not None:
            cut = score.quantile(1.0 - TOP_PCT)
            print(f"  keeping the top {TOP_PCT:.0%} of pairs by score -> cutoff {cut:.4f}")
        elif THRESHOLD is not None:
            cut = THRESHOLD
        if cut is not None:
            topic["relevant"] = (score >= cut).astype(int)
    elif THRESHOLD is not None or TOP_PCT is not None:
        print("  WARNING: relevance scores are constant; threshold ignored")
    cols = key + ["prediction"] + [c for c in ("confidence",) if c in stance.columns]
    st = stance[cols].rename(columns={"prediction": "stance_prediction"})

    out = topic.merge(st, on=key, how="left")
    out["prediction"] = out["stance_prediction"].fillna("none")
    # The parent comment travels with the pair so the interface can show it; a
    # comment whose target is only recoverable from the comment above is not
    # discarded. An earlier version dropped those, but the annotated sample says
    # they are mostly correct -- of 100 reviewed English pairs whose comment does
    # not name its target, 74 were judged correct and only 24 had the target named
    # anywhere in the thread.
    keep = ["title", "comment_id", "comment_text", "topic", "prediction", "relevant",
            "confidence", "topic_confidence", "relevance_score",
            "parent_comment_text",
            "author", "like_count", "published_date", "root_comment_id", "gold_stance"]
    out = out[[c for c in keep if c in out.columns]].copy()
    out["model_topic"], out["model_stance"] = MODELS[lang]

    dst = ROOT / "data" / "predictions" / f"{lang}_app_predictions.csv"
    out.to_csv(dst, index=False)
    rel = int(out["relevant"].sum())
    print(f"{dst.name}: {len(out)} pairs | {rel} judged relevant | "
          f"stance {out[out.relevant == 1]['prediction'].value_counts().to_dict()}")
    if "gold_stance" in out.columns:
        g = out[(out.relevant == 1) & out.gold_stance.isin(["pro", "con"])].copy()
        if len(g):
            print(f"  sanity: agrees with gold on {(g.prediction == g.gold_stance).mean():.1%} of {len(g)} gold-labelled pairs")
            # Does the model's confidence actually separate right from wrong? If it
            # does not, the app must not show it -- a meaningless badge is worse
            # than none. EN scored 0.76 and NL 0.53 (chance) in the earlier export.
            if "confidence" in g.columns and g["confidence"].notna().any():
                try:
                    from sklearn.metrics import roc_auc_score
                    correct = (g.prediction == g.gold_stance).astype(int)
                    if correct.nunique() > 1:
                        auc = roc_auc_score(correct, pd.to_numeric(g.confidence, errors="coerce").fillna(0))
                        verdict = ("usable" if auc >= 0.65 else
                                   "WEAK - do not display" if auc < 0.58 else "borderline")
                        print(f"  confidence AUROC vs correctness: {auc:.3f}  ({verdict})")
                except ImportError:
                    pass

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "en")
