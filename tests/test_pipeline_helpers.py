from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core.pipeline import WeeklyDigestPipeline
from models.evidence_card import EvidenceCard
from models.scored_item import ScoredItem
from utils.json_utils import write_json


def _card(*, published_date: str | None = None, published_at: datetime | None = None) -> EvidenceCard:
    return EvidenceCard(
        id="a1",
        source_id="source_a",
        title="title",
        summary="summary",
        links=["https://example.com/a1"],
        canonical_url="https://example.com/a1",
        published_at=published_at,
        published_date=published_date,
        source_type="primary",
        trust_tier=5,
        category="company",
        cleaned_excerpt="clean summary",
        possible_event_type="launch",
    )


def test_safe_mean_handles_empty_and_values() -> None:
    assert WeeklyDigestPipeline._safe_mean([]) == 0.0
    assert WeeklyDigestPipeline._safe_mean([1.0, 2.0, 2.0]) == 1.6667


def test_cluster_earliest_date_prefers_known_dates() -> None:
    cards_by_id = {
        "a1": _card(published_date="2026-02-10"),
        "a2": _card(published_at=datetime(2026, 2, 8, 10, 30, tzinfo=UTC)),
    }
    assert WeeklyDigestPipeline._cluster_earliest_date(["a1", "a2"], cards_by_id) == "2026-02-08"


def test_build_scored_item_handles_none_and_dict_payload() -> None:
    card = _card()
    assert WeeklyDigestPipeline._build_scored_item(card, None) is None
    scored = WeeklyDigestPipeline._build_scored_item(
        card,
        {
            "id": "a1",
            "semantic_relevance_score": 0.7,
            "semantic_importance_score": 0.8,
            "semantic_novelty_score": 0.9,
            "rationale": "good",
            "scoring_source": "llm",
        },
    )
    assert scored is not None
    assert scored.id == "a1"
    assert scored.scores.trust == 1.0
    assert scored.scores.composed == 0.815


def test_load_raw_items_from_disk_requires_list_payload(hermetic_pipeline, tmp_path) -> None:
    hermetic_pipeline.raw_items_path = tmp_path / "raw.json"
    write_json(hermetic_pipeline.raw_items_path, {"id": "bad"})
    with pytest.raises(ValueError):
        hermetic_pipeline._load_raw_items_from_disk()


def test_load_scored_items_from_disk_requires_list_payload(hermetic_pipeline, tmp_path) -> None:
    hermetic_pipeline.scored_items_path = tmp_path / "scored.json"
    write_json(hermetic_pipeline.scored_items_path, {"id": "bad"})
    with pytest.raises(ValueError):
        hermetic_pipeline._load_scored_items_from_disk()


def test_run_stage_rejects_unknown_stage(hermetic_pipeline) -> None:
    with pytest.raises(ValueError, match="Unsupported stage"):
        hermetic_pipeline.run_stage("unknown")


def test_run_cluster_stage_requires_scored_items_file(hermetic_pipeline, tmp_path) -> None:
    hermetic_pipeline.raw_items_path = tmp_path / "raw_items.json"
    write_json(hermetic_pipeline.raw_items_path, [])
    hermetic_pipeline.scored_items_path = tmp_path / "missing_scored.json"
    with pytest.raises(FileNotFoundError):
        hermetic_pipeline.run_stage("cluster")


def test_run_score_stage_writes_scored_items(hermetic_pipeline, pipeline_test_raw_items, tmp_path) -> None:
    hermetic_pipeline.raw_items_path = tmp_path / "raw_items.json"
    hermetic_pipeline.scored_items_path = tmp_path / "scored_items.json"
    write_json(hermetic_pipeline.raw_items_path, [item.model_dump() for item in pipeline_test_raw_items])

    result = hermetic_pipeline.run_stage("score")

    assert isinstance(result.scored_items, list)
    assert all(isinstance(item, ScoredItem) for item in result.scored_items)
    assert hermetic_pipeline.scored_items_path.exists()
