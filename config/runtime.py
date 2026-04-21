from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


@dataclass(frozen=True)
class RuntimeConfig:
    weekly_window_days: int
    max_items_per_source: int
    max_items_per_source_high_trust: int
    request_timeout: int
    max_retries: int
    batch_size_for_scoring: int
    embedding_model: str
    gemini_api_key: str
    gemini_model_easy: str
    gemini_model_hard: str
    base_dir: Path
    output_dir: Path
    intermediate_dir: Path
    source_registry_path: Path
    app_version: str
    log_json: bool
    crew_max_llm_attempts: int
    crew_retry_backoff_seconds: float
    crew_retry_cooldown_seconds: int

    @classmethod
    def from_env(cls) -> RuntimeConfig:
        base_dir = Path(__file__).resolve().parent.parent
        output_dir = base_dir / "outputs"
        return cls(
            weekly_window_days=_env_int("WEEKLY_WINDOW_DAYS", 7),
            max_items_per_source=_env_int("MAX_ITEMS_PER_SOURCE", 15),
            max_items_per_source_high_trust=_env_int("MAX_ITEMS_PER_SOURCE_HIGH_TRUST", 20),
            request_timeout=_env_int("REQUEST_TIMEOUT", 10),
            max_retries=_env_int("MAX_RETRIES", 3),
            batch_size_for_scoring=_env_int("BATCH_SIZE_FOR_SCORING", 15),
            embedding_model=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
            gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
            gemini_model_easy=os.getenv("GEMINI_MODEL_EASY", "gemini/gemini-2.5-flash-lite"),
            gemini_model_hard=os.getenv("GEMINI_MODEL_HARD", "gemini/gemini-2.5-flash"),
            base_dir=base_dir,
            output_dir=output_dir,
            intermediate_dir=output_dir / "intermediate",
            source_registry_path=base_dir / "config" / "source_registry.json",
            app_version=os.getenv("APP_VERSION", "0.1.0"),
            log_json=os.getenv("LOG_JSON", "false").strip().lower() in {"1", "true", "yes", "on"},
            crew_max_llm_attempts=max(1, _env_int("CREW_MAX_LLM_ATTEMPTS", 3)),
            crew_retry_backoff_seconds=max(0.0, _env_float("CREW_RETRY_BACKOFF_SECONDS", 0.75)),
            crew_retry_cooldown_seconds=max(0, _env_int("CREW_RETRY_COOLDOWN_SECONDS", 30)),
        )
