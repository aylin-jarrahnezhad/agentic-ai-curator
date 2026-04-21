# Project Overview

## What This Solution Does

`agentic-ai-curator` converts high-volume AI/data updates into a curated weekly digest.

At a high level, it:

1. Collects raw records from curated sources.
2. Normalizes and deduplicates them.
3. Scores relevance and importance.
4. Clusters related items into events/themes.
5. Produces digest outputs and diagnostics.

The result is a compact artifact you can skim quickly while still preserving traceability through stage outputs.

## Why It Exists

- **Reduce manual scanning** across many websites and feeds.
- **Improve consistency** with deterministic preprocessing plus LLM-assisted scoring/summarization.
- **Expose observability** via intermediate artifacts and diagnostics reports.

## Key Characteristics

- Local-first execution.
- Stage-oriented pipeline (`fetch`, `score`, `cluster`, `digest`).
- Typed code + test suite + lint/type/format gates.
- Reproducible outputs in `outputs/` and `outputs/intermediate/`.

## Model Choice and Portability

The current defaults use `GEMINI_MODEL_EASY` and `GEMINI_MODEL_HARD`, but the architecture is designed to be provider-swappable through service boundaries (crew/scoring abstractions).

In practice, this means:

- Gemini is the current default configuration.
- The pipeline logic itself is model-agnostic at the orchestration level.
- You can adapt the crew/model client implementation to other providers while keeping stage flow unchanged.
