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
