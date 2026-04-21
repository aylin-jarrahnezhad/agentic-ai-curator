# Architecture

## Code Layout

- `config/`: runtime/env config loading.
- `core/`: orchestration + stage entrypoints.
- `core/stages/`: stage-specific executors.
- `services/`: business logic (fetch, preprocess, scoring, clustering, digest).
- `models/`: pydantic schemas and typed payloads.
- `utils/`: helpers (dates, json, text, logging, metrics).
- `tests/`: unit/integration-style tests.

## Execution Model

The pipeline is coordinated by `WeeklyDigestPipeline` in `core/pipeline.py`.

Stages:

1. `fetch`
2. `score`
3. `cluster`
4. `digest`

Each stage writes artifacts that can be reused by downstream stages.

## Data Flow

```text
Sources -> Raw Items -> Normalized Items -> Evidence Cards -> Scored Items
      -> Clustered Items -> Events -> Digest + Diagnostics
```

## Evidence Card Shape

`EvidenceCard` is the core scoring unit produced after normalization/deduplication.
A simplified example:

```json
{
  "id": "openai_blog:2026-04-21:new-release",
  "source_id": "openai_blog",
  "title": "OpenAI announces new model updates",
  "summary": "Release notes and benchmark improvements...",
  "cleaned_excerpt": "Longer cleaned text used for scoring...",
  "links": ["https://openai.com/news/..."],
  "canonical_url": "https://openai.com/news/...",
  "published_date": "2026-04-21",
  "trust_tier": 5,
  "freshness_score": 0.94,
  "source_trust_prior": 1.0,
  "completeness_score": 0.9
}
```

These cards are then passed into semantic scoring and clustering.

## Design Choices

- **Stage artifacts** enable easier debugging and reruns.
- **Protocol-typed service boundaries** improve readability and static checks.
- **Local output store** keeps the system portable and cloud-independent.
