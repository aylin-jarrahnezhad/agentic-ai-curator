# Getting Started

## Prerequisites

- Python 3.11
- Git
- Optional: `uv` (for faster env/package workflows)

## Environment Setup

Copy and edit environment variables:

```bash
cp .env.example .env
```

Set at minimum:

- `GEMINI_API_KEY`

## Windows

### Option A: Standard `venv` + `pip`

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements-dev.txt
python run_pipeline.py --stage all
```

### Option B: `uv`

```powershell
uv venv
uv sync
uv run python run_pipeline.py --stage all
```

## macOS

### Option A: Standard `venv` + `pip`

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt
python run_pipeline.py --stage all
```

### Option B: `uv`

```bash
uv venv
uv sync
uv run python run_pipeline.py --stage all
```

## Run by Stage

```bash
python run_pipeline.py --stage fetch
python run_pipeline.py --stage score
python run_pipeline.py --stage cluster
python run_pipeline.py --stage digest
```

Use this mode when debugging a specific stage.

## Drop Article Memories into CrispyBrain

After a full run or staged run has produced outputs, export the selected article memories into CrispyBrain:

```bash
python scripts/export_crispybrain_memories.py
```

The command writes CrispyBrain inbox `.txt` files for display project `Curated Articles`.
The project key is exactly `Curated Articles`; the exporter preserves the capitalization and space in the inbox folder and Q&A project selector.
When CrispyBrain's local UI is running, use the import endpoint path:

```bash
python scripts/export_crispybrain_memories.py \
  --crispybrain-import-url http://localhost:8787/api/inbox/import
```

It uses `clustered_items.json` when available, otherwise scored items with `scores.composed >= 0.7`, otherwise raw fetched items.
