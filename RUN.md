# YouArgue — how to run it

Copy of the working demo (`demo_YouArgue`), wired to serve **model predictions**
as well as the gold annotations. Nothing here touches the original app.

## Run it (two terminals)

**1 — backend**

```bash
cd ~/Documents/GitHub/youargue_connected/backend
python3.12 -m uvicorn main:app --reload --port 8000
```

Use **python3.12** — it is the only interpreter on this machine with `fastapi`
and `uvicorn` installed. You should see:

```
EN corpus loaded: 5943 rows
NL corpus loaded: 2180 rows
Uvicorn running on http://127.0.0.1:8000
```

**2 — frontend**

```bash
cd ~/Documents/GitHub/youargue_connected/frontend
npm run dev
```

Then open **http://localhost:3000**. `node_modules` was copied across, so there
is no `npm install` step.

To stop: `Ctrl-C` in each terminal.

## Gold vs model output

Every analysis endpoint takes `?source=`:

| | |
|---|---|
| `source=gold` (default) | your human annotations — the app as it always behaved |
| `source=model` | what the trained models predict |

```bash
curl "http://localhost:8000/api/analysis/videos?lang=en&source=model"
curl "http://localhost:8000/api/analysis/topics?lang=en&title=<video title>&source=model"
curl "http://localhost:8000/api/model/status"      # which languages have predictions
```

`model_status` returns empty until the prediction files exist. The app never
breaks without them; it just keeps showing gold.

## Getting the model predictions

The models are 8–9B parameters and will not serve on this laptop (18 GB, no
CUDA), so predictions are computed on the HPC and shipped as a file.

Jobs **15748950–15748953** produce them:

| stage | job | model |
|---|---|---|
| EN topic | `app_topic_en` | `seqllm_llama_en_binary` — Llama-3.1-8B, title context |
| EN stance | `app_stance_en` | `ctx4_gemma_en_root` — Gemma-2-9B, root context |
| NL topic | `app_topic_nl` | `ctx4_gemma_nl_topic_description` — Gemma-2-9B, description |
| NL stance | `app_stance_nl` | `seqllm_gemma_nl_stance` — Gemma-2-9B, title context |

Stance runs only on the pairs the topic model kept, and each stance job waits
for its topic job (`-W depend=afterok`). Check them with:

```bash
ssh hpc 'bash -lc "module swap cluster/accelgor; squeue -u vsc47819"'
```

When all four are done:

```bash
cd ~/Documents/GitHub/youargue_connected
bash tools/fetch_predictions.sh
curl -X POST http://localhost:8000/api/model/reload
```

That pulls both prediction files per language, merges them into
`data/predictions/<lang>_app_predictions.csv`, and prints a sanity check —
how often the model agrees with your gold labels on the pairs that have them.

## If something goes wrong

| symptom | cause |
|---|---|
| `ModuleNotFoundError: fastapi` | wrong interpreter — use `python3.12` |
| `Address already in use` | an old backend is running: `pkill -f "uvicorn main:app"` |
| frontend loads but no data | backend not running, or not on port 8000 (the frontend expects it) |
| `Could not load EN corpus` | run the backend from inside `backend/`, not the repo root |
| `model_status` empty after fetching | check `data/predictions/*_app_predictions.csv` exists and has the required columns |
| HPC commands fail with `Permission denied (publickey)` | `ssh-add --apple-load-keychain` |

## Layout

```
backend/main.py                 API; ?source=gold|model on the analysis routes
backend/model_predictions.py    loads and serves the model output
data/youtube_corpus/            gold annotations (EN, NL)
data/predictions/               model output; empty until fetched
tools/fetch_predictions.sh      pull from HPC and merge
tools/merge_predictions.py      topic + stance -> the app's file
frontend/                       Next.js UI
```
