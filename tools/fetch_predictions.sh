#!/bin/bash
# Pull the finished model predictions off the HPC and build the app's file.
#   bash tools/fetch_predictions.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE=/data/gent/vo/000/gvo00042/vsc47819/demo_paper/outputs_human
mkdir -p "$ROOT/data/predictions/raw"

for L in en nl de fr ru; do
  case $L in en) TC=none;;  nl) TC=description;; *) TC=title;;  esac
  case $L in en) SC=root;;  nl) SC=title;;       *) SC=root;;   esac
  # the original single-video runs. Only English and Dutch ever had them, so a
  # missing file here is normal rather than an error.
  scp -q "hpc:$REMOTE/app_topic_$L/$TC/0shot/app_pairs_predictions.csv"  "$ROOT/data/predictions/raw/${L}_topic_predictions.csv"  2>/dev/null || true
  scp -q "hpc:$REMOTE/app_stance_$L/$SC/0shot/app_pairs_predictions.csv" "$ROOT/data/predictions/raw/${L}_stance_predictions.csv" 2>/dev/null || true
  # batch runs: recent videos collected from the channel, analysed together
  if scp -q "hpc:$REMOTE/batch_${L}_topic/$TC/0shot/app_pairs_predictions.csv" \
        "$ROOT/data/predictions/raw/${L}_batch_topic_predictions.csv" 2>/dev/null; then
     scp -q "hpc:$REMOTE/batch_${L}_stance/$SC/0shot/app_pairs_predictions.csv" \
        "$ROOT/data/predictions/raw/${L}_batch_stance_predictions.csv" 2>/dev/null || true
  fi

  # the unseen-video run, if it has finished
  if scp -q "hpc:$REMOTE/nv_topic_$L/title/0shot/app_pairs_predictions.csv" \
        "$ROOT/data/predictions/raw/${L}_newvideo_topic_predictions.csv" 2>/dev/null; then
     scp -q "hpc:$REMOTE/nv_stance_$L/root/0shot/app_pairs_predictions.csv" \
        "$ROOT/data/predictions/raw/${L}_newvideo_stance_predictions.csv" 2>/dev/null || true
  fi

  # the curated-shortlist run: pairs built by matching the curated inventory
  # against each video, rather than by embedding similarity over a topic pool
  if scp -q "hpc:$REMOTE/nvc_${L}_topic/$TC/0shot/app_pairs_predictions.csv" \
        "$ROOT/data/predictions/raw/${L}_curated_topic_predictions.csv" 2>/dev/null; then
     scp -q "hpc:$REMOTE/nvc_${L}_stance/$SC/0shot/app_pairs_predictions.csv" \
        "$ROOT/data/predictions/raw/${L}_curated_stance_predictions.csv" 2>/dev/null || true
  fi
  python3 "$ROOT/tools/merge_predictions.py" "$L"
done
echo "Done. Restart the backend, or: curl -X POST http://localhost:8000/api/model/reload"
