# YouArgue — Political Opinion Monitoring

Multilingual political opinion monitoring over YouTube news comment sections in
English, Dutch, German, French and Russian. Given a video, the system selects
candidate stance targets from a curated inventory by matching per-language
surface forms, scores every comment against the surviving candidates for
relevance, and classifies the accepted pairs as pro or con.

Companion demo for the EACL 2027 system demonstration paper.

**This is a demonstration snapshot, not the full system.** It contains the
interface and the model output for 27 videos across five broadcaster channels,
frozen at the time of writing, so that the results reported in the paper can be
inspected and reproduced. The trained adapters are not included -- they are
available under gated access on Hugging Face -- and the training code is not
part of this release. Analysing a new video therefore requires the models,
obtained separately.

## Running it

The **analysis view works out of the box** — it serves model predictions bundled
with this repository and needs no API key and no GPU.

**macOS / Linux**

```bash
# backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# frontend, in a second terminal
cd frontend
npm install
npm run dev          # http://localhost:3000
```

**Windows (PowerShell)**

```powershell
# backend
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# frontend, in a second terminal
cd frontend
npm install
npm run dev          # http://localhost:3000
```

If PowerShell blocks the activation script, run
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first, or use
`.venv\Scripts\activate.bat` from cmd.exe.

Open <http://localhost:3000/analysis>, pick a language and a video, and click any
target to see the comments on each side, ordered by model confidence.

## The dashboard and live retrieval

The demonstration video shows the system running against the live YouTube Data
API. This package reproduces everything except live retrieval: without a key
the dashboard serves a frozen snapshot of 2025 regardless of the date window
selected, so the video list will differ from the one in the video. The analysis
view is identical either way. To fetch live data, put your own key in
`.env` (see `.env.example`):

```
YOUTUBE_API=your-key-here
```

Analysing a *new* video additionally requires `tools/requirements.txt` and a
GPU: `tools/analyse_video.py` fetches the comments, matches the curated
inventory against them, and runs the relevance and stance models. The bundled
predictions were produced this way.

## What is included

| | |
|---|---|
| `data/predictions_deploy/` | model predictions for 27 videos across 5 channels |
| `data/youtube_corpus/` | the annotated corpora |
| `data/dashboard_snapshot.json` | frozen dashboard data, so the demo runs keyless |
| `topic_pool/` | the curated inventory: 246 targets, 2,665 surface forms |
| `tools/` | the analysis pipeline |

## Licence and use

**This snapshot is provided for peer review and academic research only, to
demonstrate the system described in the paper.**
The annotated corpora, the model predictions and the curated inventory may be
used to verify and build on the work described in the paper. They may not be
used commercially, to profile individuals, or to train systems for either
purpose.

Code is released under the MIT licence (`LICENSE`). The curated target
inventory and our annotations are released under CC BY-NC 4.0, which permits
reuse with attribution for non-commercial purposes.

The relevance and stance adapters are LoRA weights over Gemma-2-9B-it and are
therefore governed by the **Gemma Terms of Use**, not by an open-source licence.

Comment text is redistributed subject to YouTube's Terms of Service. Usernames
are replaced by a placeholder in every file.
