"""Model predictions for the app.

The demo originally displayed gold annotations. This module serves the same
shape from actual model output, so the app demonstrates the system rather than
the annotation. Gold stays the default: if no prediction file is present the
app behaves exactly as before.

Expected file: data/predictions/<lang>_app_predictions.csv, one row per
(comment, topic) pair, with at least:
    title, comment_id, comment_text, topic, prediction   (pro | con | none)
and optionally: relevant (0/1), confidence (0-1), author, like_count,
published_date, root_comment_text, model_topic, model_stance.
"""
from pathlib import Path
import pandas as pd

PRED_ROOT = Path(__file__).parent.parent / "data" / "predictions_deploy"
ALIAS_PATH = Path(__file__).parent.parent / "data" / "topic_aliases.json"
PREDICTIONS: dict = {}
MODEL_INFO: dict = {}
# Per-language confidence cut points. A fine-tuned adapter is heavily
# overconfident -- median 0.99, so fixed 0.8/0.6 thresholds label ~90% of
# comments "high" and the badge says nothing. The model's *ranking* is what
# carries signal (AUROC 0.76 EN / 0.85 NL), so bin by tercile within a language.
CONF_CUTS: dict = {}

_ALIASES = {
    "video": "title", "comment": "comment_text", "text": "comment_text",
    "pred": "prediction", "pred_stance": "prediction", "likes": "like_count",
}


def topic_aliases(lang: str) -> dict:
    """Surface-form aliases in the gold labels ('usa' and 'the usa' are one target)."""
    try:
        import json
        return {k: v for k, v in json.loads(ALIAS_PATH.read_text(encoding="utf-8")).get(lang, {}).items()}
    except Exception:
        return {}


def load_predictions() -> None:
    """Load every <lang>_app_predictions.csv found. Missing files are not an error."""
    PREDICTIONS.clear()
    MODEL_INFO.clear()
    if not PRED_ROOT.exists():
        return
    for path in sorted(PRED_ROOT.glob("*_app_predictions.csv")):
        lang = path.name.split("_")[0]
        try:
            df = pd.read_csv(path)
        except Exception as e:                       # a broken file must not stop the app
            print(f"Could not load predictions for {lang}: {e}")
            continue
        df = df.rename(columns={k: v for k, v in _ALIASES.items() if k in df.columns})
        missing = {"title", "comment_id", "comment_text", "topic", "prediction"} - set(df.columns)
        if missing:
            print(f"Predictions for {lang} ignored -- missing columns: {sorted(missing)}")
            continue
        if "relevant" in df.columns:                 # drop pairs the topic model rejected
            df = df[df["relevant"].astype(str).isin(("1", "1.0", "True", "true"))]
        df["prediction"] = df["prediction"].astype(str).str.strip().str.lower()
        alias = topic_aliases(lang)
        if alias:
            df["topic"] = df["topic"].astype(str).str.strip().str.lower().replace(alias)
            # one comment can now hold the same topic twice, once per spelling
            df = df.drop_duplicates(subset=["comment_id", "topic"], keep="first")
        conf = pd.to_numeric(df.get("confidence"), errors="coerce") if "confidence" in df.columns else None
        if conf is not None and conf.notna().sum() > 30:
            CONF_CUTS[lang] = (float(conf.quantile(1 / 3)), float(conf.quantile(2 / 3)))
        PREDICTIONS[lang] = df
        MODEL_INFO[lang] = {
            "rows": int(len(df)),
            "videos": int(df["title"].nunique()),
            "topic_model": str(df["model_topic"].iloc[0]) if "model_topic" in df.columns and len(df) else "unknown",
            "stance_model": str(df["model_stance"].iloc[0]) if "model_stance" in df.columns and len(df) else "unknown",
            "file": path.name,
        }
        cuts = CONF_CUTS.get(lang)
        print(f"{lang.upper()} predictions loaded: {len(df)} rows, {df['title'].nunique()} videos"
              + (f", confidence terciles {cuts[0]:.3f}/{cuts[1]:.3f}" if cuts else ""))


def _confidence_label(v, lang: str = "") -> str:
    """Rank-based within a language; falls back to absolute cut points."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v).lower() if str(v).lower() in ("high", "medium", "low") else "medium"
    if f != f:                                   # NaN
        return "medium"
    lo, hi = CONF_CUTS.get(lang, (0.6, 0.8))
    return "high" if f >= hi else "medium" if f >= lo else "low"


_WEIGHT = {"high": 1.5, "medium": 1.0, "low": 0.6}


def _rank(df, lang=""):
    """Most certain first, least certain last."""
    if df.empty:
        return df
    conf = pd.to_numeric(df.get("confidence"), errors="coerce").fillna(0)
    return df.assign(_conf=conf).sort_values("_conf", ascending=False)


def topics_for_video(title: str, lang: str, min_total: int = 2, limit: int = 15) -> dict:
    """Same response shape as the gold endpoint, built from model predictions."""
    empty = {"title": title, "lang": lang, "source": "model", "total_comments": 0,
             "thread_count": 0, "topic_count": 0, "topics": []}
    if lang not in PREDICTIONS:
        return empty
    vdf = PREDICTIONS[lang][PREDICTIONS[lang]["title"] == title]
    if vdf.empty:
        return empty

    def fmt(rows, topic=None) -> list:          # noqa: D401 - lang closed over from the caller
        out = []
        for _, r in rows.head(limit).iterrows():
            out.append({
                "comment_id": str(r.get("comment_id", "")),
                "text": str(r.get("comment_text", "")),
                "author": str(r.get("author", "Anonymous")),
                "likes": int(r.get("like_count", 0) or 0),
                "date": str(r.get("published_date", ""))[:10],
                "argument_type": "",
                "confidence": _confidence_label(r.get("confidence", ""), lang),
            })
        return out

    topics = []
    for topic, tdf in vdf.groupby("topic"):
        pro = tdf[tdf["prediction"] == "pro"]
        con = tdf[tdf["prediction"] == "con"]
        total = len(pro) + len(con)
        if total < min_total:
            continue
        # Rank examples the way the gold path does -- visibility first, discounted
        # by uncertainty -- not by confidence alone. Sorting on confidence would
        # surface only the model's easiest calls and make every badge read "high".
        pro, con = _rank(pro, lang), _rank(con, lang)
        pro_pct = round(len(pro) / total * 100)
        topics.append({
            "topic": str(topic), "pro_count": len(pro), "con_count": len(con),
            "total": total, "pro_pct": pro_pct, "con_pct": 100 - pro_pct,
            "pro_comments": fmt(pro, topic), "con_comments": fmt(con, topic),
        })
    topics.sort(key=lambda t: t["total"], reverse=True)
    return {"title": title, "lang": lang, "source": "model",
            "total_comments": int(vdf["comment_id"].nunique()),
            "thread_count": int(vdf["root_comment_id"].nunique()) if "root_comment_id" in vdf.columns else 0,
            "topic_count": len(topics), "topics": topics}


def videos_with_predictions(lang: str) -> list:
    if lang not in PREDICTIONS:
        return []
    df = PREDICTIONS[lang]
    g = df.groupby("title")["comment_id"].nunique().reset_index()
    g.columns = ["title", "comment_count"]
    return g.sort_values("comment_count", ascending=False).to_dict(orient="records")
