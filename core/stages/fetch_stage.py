from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from config.settings import INTERMEDIATE_DIR, SOURCE_REGISTRY_PATH
from core.orchestrator import PipelineResult
from models.pipeline_types import SourceConfig
from models.raw_item import RawItem
from utils.json_utils import read_json, write_json


class FetchService(Protocol):
    def fetch_all(self, sources: list[SourceConfig]) -> tuple[list[RawItem], dict[str, str]]: ...


class FetchStage:
    def __init__(
        self,
        fetch_service: FetchService,
        raw_items_path: Path,
        base_item_builder: Callable[[str, str, str, list[str], dict[str, Any]], dict[str, Any]],
    ) -> None:
        self.fetch_service = fetch_service
        self.raw_items_path = raw_items_path
        self.base_item_builder = base_item_builder

    @staticmethod
    def _load_sources() -> list[SourceConfig]:
        payload = read_json(SOURCE_REGISTRY_PATH)
        sources = payload.get("sources") if isinstance(payload, dict) else None
        if not isinstance(sources, list):
            raise ValueError(f"Invalid source registry format at {SOURCE_REGISTRY_PATH}")
        out: list[SourceConfig] = []
        for source in sources:
            if not isinstance(source, dict):
                continue
            source_id = source.get("source_id")
            connector = source.get("connector")
            if not isinstance(source_id, str) or not source_id:
                continue
            if not isinstance(connector, str) or not connector:
                continue
            out.append(source)
        return out

    @staticmethod
    def _error_type(error_message: str) -> str:
        normalized = error_message.lower()
        if "unknown connector" in normalized:
            return "unknown_connector"
        if "timeout" in normalized or "timed out" in normalized:
            return "timeout"
        if "retries exhausted" in normalized:
            return "retries_exhausted"
        return "fetch_error"

    @staticmethod
    def _build_fetch_report(
        sources: list[SourceConfig],
        raw_items: list[RawItem],
        failures: dict[str, str],
        source_stats: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        counts_by_source = Counter(item.source_id for item in raw_items)
        stats_by_source: dict[str, dict[str, Any]] = {}
        if source_stats:
            for row in source_stats:
                source_id = row.get("source_id")
                if isinstance(source_id, str) and source_id:
                    stats_by_source[source_id] = row
        per_source: list[dict[str, Any]] = []
        for source in sources:
            source_id = source["source_id"]
            source_row = stats_by_source.get(source_id, {})
            error_message = str(source_row.get("error_message") or failures.get(source_id, ""))
            status = str(source_row.get("status") or ("failed" if error_message else "succeeded"))
            items_extracted = int(source_row.get("items_fetched", counts_by_source.get(source_id, 0)))
            error_type = FetchStage._error_type(error_message) if error_message else ""
            per_source.append(
                {
                    "source_id": source_id,
                    "connector": source["connector"],
                    "items_extracted": items_extracted,
                    "status": status,
                    "error_type": error_type,
                    "error_message": error_message,
                }
            )
        known_source_ids = {source["source_id"] for source in sources}
        for source_id, error_message in failures.items():
            if source_id in known_source_ids:
                continue
            per_source.append(
                {
                    "source_id": source_id,
                    "connector": "unknown",
                    "items_extracted": 0,
                    "status": "failed",
                    "error_type": FetchStage._error_type(error_message),
                    "error_message": error_message,
                }
            )
        per_source.sort(key=lambda row: row["source_id"])
        error_type_counts = Counter(row["error_type"] for row in per_source if row["error_type"])
        return {
            "generated_at": datetime.now(tz=UTC).isoformat(),
            "totals": {
                "sources_configured": len(sources),
                "sources_succeeded": sum(1 for row in per_source if row["status"] == "succeeded"),
                "sources_failed": sum(1 for row in per_source if row["status"] == "failed"),
                "sources_with_items": sum(1 for row in per_source if row["items_extracted"] > 0),
                "items_extracted_total": len(raw_items),
            },
            "error_type_counts": dict(error_type_counts),
            "sources": per_source,
        }

    @staticmethod
    def _build_fetch_summary_markdown(report: dict[str, Any]) -> str:
        totals = report["totals"]
        lines = [
            "# Fetch Report Summary",
            "",
            "## Totals",
            f"- Sources configured: {totals['sources_configured']}",
            f"- Sources succeeded: {totals['sources_succeeded']}",
            f"- Sources failed: {totals['sources_failed']}",
            f"- Sources with extracted items: {totals['sources_with_items']}",
            f"- Total items extracted: {totals['items_extracted_total']}",
            "",
            "## Per Source",
            "",
            "| Source | Connector | Status | Items | Error Type |",
            "|---|---|---:|---:|---|",
        ]
        for source_row in report["sources"]:
            lines.append(
                "| "
                f"{source_row['source_id']} | {source_row['connector']} | {source_row['status']} | "
                f"{source_row['items_extracted']} | {source_row['error_type'] or '-'} |"
            )
        failed_rows = [row for row in report["sources"] if row["status"] == "failed"]
        if failed_rows:
            lines.extend(["", "## Failure Details"])
            for row in failed_rows:
                lines.append(f"- `{row['source_id']}` ({row['error_type']}): {row['error_message']}")
        return "\n".join(lines) + "\n"

    def run(self) -> PipelineResult:
        sources = self._load_sources()
        raw_items, failures = self.fetch_service.fetch_all(sources)
        source_stats: list[dict[str, Any]] | None = None
        get_stats = getattr(self.fetch_service, "get_last_fetch_stats", None)
        if callable(get_stats):
            stats_payload = get_stats()
            if isinstance(stats_payload, list):
                source_stats = [row for row in stats_payload if isinstance(row, dict)]
        write_json(
            self.raw_items_path,
            [self.base_item_builder(r.id, r.title, r.summary, r.links, r.model_dump()) for r in raw_items],
            preserve_if_empty_would_erase=True,
        )
        report = self._build_fetch_report(sources, raw_items, failures, source_stats=source_stats)
        write_json(INTERMEDIATE_DIR / "fetch_report.json", report)
        (INTERMEDIATE_DIR / "fetch_report_summary.md").write_text(
            self._build_fetch_summary_markdown(report),
            encoding="utf-8",
        )
        return PipelineResult(
            fetched_count=len(raw_items),
            normalized_count=0,
            evidence_count=0,
            refined_event_count=0,
            digest_path=None,
            diagnostics_path=None,
            scored_items=[],
            events=[],
        )
