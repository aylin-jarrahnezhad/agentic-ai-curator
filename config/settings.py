from __future__ import annotations

from config.runtime import RuntimeConfig

RUNTIME = RuntimeConfig.from_env()

WEEKLY_WINDOW_DAYS = RUNTIME.weekly_window_days
MAX_ITEMS_PER_SOURCE = RUNTIME.max_items_per_source
MAX_ITEMS_PER_SOURCE_HIGH_TRUST = RUNTIME.max_items_per_source_high_trust
REQUEST_TIMEOUT = RUNTIME.request_timeout
MAX_RETRIES = RUNTIME.max_retries
BATCH_SIZE_FOR_SCORING = RUNTIME.batch_size_for_scoring
EMBEDDING_MODEL = RUNTIME.embedding_model
GEMINI_API_KEY = RUNTIME.gemini_api_key
GEMINI_MODEL_EASY = RUNTIME.gemini_model_easy
GEMINI_MODEL_HARD = RUNTIME.gemini_model_hard
BASE_DIR = RUNTIME.base_dir
OUTPUT_DIR = RUNTIME.output_dir
INTERMEDIATE_DIR = RUNTIME.intermediate_dir
SOURCE_REGISTRY_PATH = RUNTIME.source_registry_path
CREW_MAX_LLM_ATTEMPTS = RUNTIME.crew_max_llm_attempts
CREW_RETRY_BACKOFF_SECONDS = RUNTIME.crew_retry_backoff_seconds
CREW_RETRY_COOLDOWN_SECONDS = RUNTIME.crew_retry_cooldown_seconds
