from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TypedDict

from config.settings import (
    MAX_ITEMS_PER_SOURCE,
    MAX_ITEMS_PER_SOURCE_HIGH_TRUST,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
)
from models.pipeline_types import SourceConfig
from models.raw_item import RawItem
from services.fetch.api_fetcher import APIFetcher
from services.fetch.html_fetcher import HTMLFetcher
from services.fetch.rss_fetcher import RSSFetcher
from services.fetch.social_fetcher import SocialFetcher
from utils.logging_utils import get_logger

logger = get_logger(__name__)


class SourceFetchStat(TypedDict):
    source_id: str
    connector: str
    items_fetched: int
    status: str
    error_message: str


class SourceFetchService:
    """Fetch raw items from all configured sources."""

    def __init__(self) -> None:
        self.rss = RSSFetcher()
        self.html = HTMLFetcher(timeout=REQUEST_TIMEOUT)
        self.api = APIFetcher(timeout=REQUEST_TIMEOUT)
        self.social = SocialFetcher(timeout=REQUEST_TIMEOUT)
        self._last_fetch_stats: list[SourceFetchStat] = []

    def _fetch_one(self, source: SourceConfig) -> tuple[list[RawItem], str | None]:
        connector = source["connector"]
        max_items = self._max_items_for_source(source)
        for attempt in range(MAX_RETRIES + 1):
            try:
                if connector == "rss":
                    return self.rss.fetch(source, max_items), None
                if connector == "html":
                    return self.html.fetch(source, max_items), None
                if connector in {"arxiv", "crossref", "semantic_scholar"}:
                    return self.api.fetch(source, max_items), None
                if connector == "social":
                    return self.social.fetch(source, max_items), None
                return [], f"Unknown connector: {connector}"
            except Exception as exc:
                if attempt >= MAX_RETRIES:
                    return [], str(exc)
        return [], "Retries exhausted"

    @staticmethod
    def _max_items_for_source(source: SourceConfig) -> int:
        return MAX_ITEMS_PER_SOURCE_HIGH_TRUST if int(source.get("trust_tier", 0) or 0) >= 5 else MAX_ITEMS_PER_SOURCE

    def fetch_all_with_stats(
        self, sources: list[SourceConfig]
    ) -> tuple[list[RawItem], dict[str, str], list[SourceFetchStat]]:
        all_items: list[RawItem] = []
        failures: dict[str, str] = {}
        stats: list[SourceFetchStat] = []
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(self._fetch_one, src): src for src in sources}
            for future in as_completed(futures):
                source = futures[future]
                items, error = future.result()
                all_items.extend(items)
                if error:
                    failures[source["source_id"]] = error
                    logger.warning("Fetch failure for %s: %s", source["source_id"], error)
                stats.append(
                    {
                        "source_id": source["source_id"],
                        "connector": source["connector"],
                        "items_fetched": len(items),
                        "status": "failed" if error else "succeeded",
                        "error_message": error or "",
                    }
                )
        self._last_fetch_stats = list(stats)
        return all_items, failures, stats

    def fetch_all(self, sources: list[SourceConfig]) -> tuple[list[RawItem], dict[str, str]]:
        all_items, failures, _ = self.fetch_all_with_stats(sources)
        return all_items, failures

    def get_last_fetch_stats(self) -> list[SourceFetchStat]:
        return list(self._last_fetch_stats)
