from statistics import mean
from typing import Any

from models.diagnostics import Diagnostics
from models.event import Event
from models.evidence_card import EvidenceCard
from models.normalized_item import NormalizedItem


class DiagnosticsService:
    def build(
        self,
        normalized: list[NormalizedItem],
        cards: list[EvidenceCard],
        events: list[Event],
        failures: dict[str, str],
        stage_counts: dict[str, int],
        dropped: dict[str, int],
        fetch_report: dict[str, Any] | None = None,
    ) -> Diagnostics:
        source_yield: dict[str, int] = {}
        for item in normalized:
            source_yield[item.source_id] = source_yield.get(item.source_id, 0) + 1
        topic_yield: dict[str, int] = {}
        for card in cards:
            for topic in card.likely_topic_buckets:
                topic_yield[topic] = topic_yield.get(topic, 0) + 1
        score_dist = {
            "event_mean_composed_avg": (
                round(mean([event.score.mean_composed for event in events]), 4) if events else 0.0
            ),
            "event_combined_avg": (round(mean([event.score.combined_score for event in events]), 4) if events else 0.0),
        }
        fetch_totals: dict[str, int] = {}
        fetch_error_type_counts: dict[str, int] = {}
        fetch_zero_item_sources: list[str] = []
        connector_failures = dict(failures)
        if fetch_report:
            raw_totals = fetch_report.get("totals")
            if isinstance(raw_totals, dict):
                fetch_totals = {
                    str(k): int(v) for k, v in raw_totals.items() if isinstance(k, str) and isinstance(v, int | float)
                }
            raw_error_counts = fetch_report.get("error_type_counts")
            if isinstance(raw_error_counts, dict):
                fetch_error_type_counts = {
                    str(k): int(v)
                    for k, v in raw_error_counts.items()
                    if isinstance(k, str) and isinstance(v, int | float)
                }
            raw_sources = fetch_report.get("sources")
            if isinstance(raw_sources, list):
                for row in raw_sources:
                    if not isinstance(row, dict):
                        continue
                    source_id = row.get("source_id")
                    items_extracted = row.get("items_extracted")
                    status = row.get("status")
                    error_message = row.get("error_message")
                    if (
                        isinstance(source_id, str)
                        and isinstance(items_extracted, int | float)
                        and int(items_extracted) == 0
                    ):
                        fetch_zero_item_sources.append(source_id)
                    if (
                        isinstance(source_id, str)
                        and status == "failed"
                        and isinstance(error_message, str)
                        and error_message
                    ):
                        connector_failures[source_id] = error_message
        return Diagnostics(
            fetch_totals=fetch_totals,
            fetch_error_type_counts=fetch_error_type_counts,
            fetch_zero_item_sources=sorted(set(fetch_zero_item_sources)),
            source_yield=source_yield,
            topic_yield=topic_yield,
            dropped_items_summary=dropped,
            cluster_counts={"refined_events": len(events)},
            score_distributions=score_dist,
            connector_failures=connector_failures,
            pipeline_stage_counts=stage_counts,
        )

    @staticmethod
    def to_markdown(diagnostics: Diagnostics) -> str:
        fetch_totals = diagnostics.fetch_totals or {}
        failed_sources = len(diagnostics.connector_failures)
        zero_sources = len(diagnostics.fetch_zero_item_sources)
        stage_counts = diagnostics.pipeline_stage_counts
        score = diagnostics.score_distributions

        lines = [
            "# Weekly Diagnostics",
            "",
            "## Summary",
            f"- Raw items: {stage_counts.get('raw_items', 0)}",
            f"- Normalized items: {stage_counts.get('normalized_items', 0)}",
            f"- Evidence cards: {stage_counts.get('evidence_cards', 0)}",
            f"- Refined events: {stage_counts.get('events', 0)}",
            f"- Failed fetch sources: {failed_sources}",
            f"- Zero-item fetch sources: {zero_sources}",
            "",
            "## Fetch Health",
            f"- Sources configured: {fetch_totals.get('sources_configured', 0)}",
            f"- Sources succeeded: {fetch_totals.get('sources_succeeded', 0)}",
            f"- Sources failed: {fetch_totals.get('sources_failed', failed_sources)}",
            f"- Sources with items: {fetch_totals.get('sources_with_items', 0)}",
            f"- Total extracted: {fetch_totals.get('items_extracted_total', stage_counts.get('raw_items', 0))}",
        ]

        if diagnostics.fetch_error_type_counts:
            lines.extend(["", "### Error Types"])
            for error_type, count in sorted(diagnostics.fetch_error_type_counts.items(), key=lambda x: (-x[1], x[0])):
                lines.append(f"- {error_type}: {count}")

        if diagnostics.connector_failures:
            lines.extend(["", "### Failed Sources"])
            for source_id, message in sorted(diagnostics.connector_failures.items()):
                lines.append(f"- `{source_id}`: {message}")

        if diagnostics.fetch_zero_item_sources:
            lines.extend(["", "### Zero-Item Sources (Top 15)"])
            for source_id in diagnostics.fetch_zero_item_sources[:15]:
                lines.append(f"- `{source_id}`")
            if len(diagnostics.fetch_zero_item_sources) > 15:
                lines.append(f"- ... and {len(diagnostics.fetch_zero_item_sources) - 15} more")

        lines.extend(
            [
                "",
                "## Scoring Quality",
                f"- Mean event composed score: {score.get('event_mean_composed_avg', 0.0):.4f}",
                f"- Mean event combined score: {score.get('event_combined_avg', 0.0):.4f}",
                "",
                "## Drops",
            ]
        )

        if diagnostics.dropped_items_summary:
            for reason, count in sorted(diagnostics.dropped_items_summary.items(), key=lambda x: (-x[1], x[0])):
                lines.append(f"- {reason}: {count}")
        else:
            lines.append("- No dropped-item counters recorded.")

        lines.extend(["", "## Topic Yield (Top 10)"])
        if diagnostics.topic_yield:
            for topic, count in sorted(diagnostics.topic_yield.items(), key=lambda x: (-x[1], x[0]))[:10]:
                lines.append(f"- {topic}: {count}")
        else:
            lines.append("- No topic labels available.")

        lines.extend(["", "## Actions"])
        if failed_sources > 0:
            lines.append("- Review failed source connectors and error messages.")
        if zero_sources > 0:
            lines.append("- Review zero-item sources for stale feeds/selectors/rate limits.")
        if failed_sources == 0 and zero_sources == 0:
            lines.append("- Fetch health looks stable.")
        lines.append("- Track changes weekly to spot degradation trends.")
        return "\n".join(lines) + "\n"
