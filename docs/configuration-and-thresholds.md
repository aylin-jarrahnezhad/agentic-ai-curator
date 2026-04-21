# Configuration and Thresholds

## Runtime Configuration

Configuration is loaded from environment variables by `config/runtime.py`.

Primary variables (from `.env.example`):

- `WEEKLY_WINDOW_DAYS` (default `7`)
- `MAX_ITEMS_PER_SOURCE` (default `15`)
- `MAX_ITEMS_PER_SOURCE_HIGH_TRUST` (default `20`)
- `REQUEST_TIMEOUT` (default `10`)
- `MAX_RETRIES` (default `3`)
- `BATCH_SIZE_FOR_SCORING` (default `15`)
- `EMBEDDING_MODEL` (default `all-MiniLM-L6-v2`)
- `GEMINI_MODEL_EASY`, `GEMINI_MODEL_HARD`
- `GEMINI_API_KEY`

Additional crew retry controls:

- `CREW_MAX_LLM_ATTEMPTS` (default `3`)
- `CREW_RETRY_BACKOFF_SECONDS` (default `0.75`)
- `CREW_RETRY_COOLDOWN_SECONDS` (default `30`)

## Hard-Coded Decisions in Code

These are intentionally fixed in code (not env-driven) today:

- `RELEVANCE_THRESHOLD_FOR_CLUSTERING = 0.5`  
  Used to exclude low-relevance scored items before clustering.

- `SCORING_PARALLEL_WORKERS = 2`  
  Controls semantic scoring concurrency in pipeline orchestration.
  **Note:** keep this low unless your model/provider limits allow higher concurrency; increasing it too much can trigger API throttling (for example HTTP 429 responses).

- `ClusterStage.RELEVANCE_THRESHOLD_FOR_CLUSTERING = 0.5`  
  Stage-level equivalent used when running cluster stage directly.

## Why These Defaults Exist

- **7-day window** keeps digest weekly and focused.
- **Per-source caps** limit noisy/outlier sources.
- **Timeout + retries** reduce transient fetch failures.
- **0.5 relevance floor** aims to avoid weak clusters.
- **Small parallel worker count** balances speed with API/resource stability.

## Tuning Guidance

- Increase `MAX_ITEMS_PER_SOURCE*` only if source coverage is too thin.
- Increase `REQUEST_TIMEOUT` for slow endpoints.
- Raise `RELEVANCE_THRESHOLD_FOR_CLUSTERING` for stricter event quality.
- Lower `BATCH_SIZE_FOR_SCORING` if LLM scoring payloads are unstable.
