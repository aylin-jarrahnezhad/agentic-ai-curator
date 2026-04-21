# Pipeline Stages

## `fetch`

- Loads configured sources from `config/source_registry.json`.
- Fetches records via connector-specific fetchers.
- Writes:
  - `outputs/intermediate/raw_items.json`
  - `outputs/intermediate/fetch_report.json`
  - `outputs/intermediate/fetch_report_summary.md`

## `score`

- Normalizes raw items and filters by time window.
- Deduplicates items.
- Builds evidence cards + deterministic pre-scores.
- Calls semantic scoring crew and writes:
  - `outputs/intermediate/scored_items.json`

## `cluster`

- Filters scored items by relevance threshold.
- Clusters cards and applies refinement logic.
- Writes:
  - `outputs/intermediate/clustered_items.json`

## `digest`

- Composes digest sections and renders:
  - Markdown digest
  - HTML digest
  - `latest.html` alias
  - diagnostics markdown

## Full Run (`--stage all`)

Executes all stages in sequence and returns final counts/paths.
