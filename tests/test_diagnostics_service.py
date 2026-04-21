from models.diagnostics import Diagnostics
from services.digest.diagnostics_service import DiagnosticsService


def test_to_markdown_contains_fetch_health_sections() -> None:
    diagnostics = Diagnostics(
        fetch_totals={
            "sources_configured": 5,
            "sources_succeeded": 4,
            "sources_failed": 1,
            "sources_with_items": 3,
            "items_extracted_total": 27,
        },
        fetch_error_type_counts={"timeout": 1},
        fetch_zero_item_sources=["source_x", "source_y"],
        connector_failures={"source_x": "timeout"},
        pipeline_stage_counts={
            "raw_items": 27,
            "normalized_items": 22,
            "evidence_cards": 14,
            "events": 6,
        },
        dropped_items_summary={"dedupe_dropped": 3},
        topic_yield={"llm": 7, "agents": 3},
        score_distributions={"event_mean_composed_avg": 0.71, "event_combined_avg": 0.68},
    )

    out = DiagnosticsService.to_markdown(diagnostics)

    assert "## Fetch Health" in out
    assert "### Error Types" in out
    assert "### Failed Sources" in out
    assert "### Zero-Item Sources" in out
    assert "## Actions" in out
    assert "`source_x`" in out
