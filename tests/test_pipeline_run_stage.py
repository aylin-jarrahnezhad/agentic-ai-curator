from __future__ import annotations

from utils.json_utils import write_json


def test_run_stage_flow_fetch_to_digest(monkeypatch, hermetic_pipeline, pipeline_test_raw_items, tmp_path) -> None:
    hermetic_pipeline.raw_items_path = tmp_path / "raw_items.json"
    hermetic_pipeline.scored_items_path = tmp_path / "scored_items.json"
    hermetic_pipeline.clustered_items_path = tmp_path / "clustered_items.json"

    monkeypatch.setattr(hermetic_pipeline.fetcher, "fetch_all", lambda _sources: (pipeline_test_raw_items, {}))

    fetch_result = hermetic_pipeline.run_stage("fetch")
    score_result = hermetic_pipeline.run_stage("score")
    cluster_result = hermetic_pipeline.run_stage("cluster")
    digest_result = hermetic_pipeline.run_stage("digest")

    assert fetch_result.fetched_count == len(pipeline_test_raw_items)
    assert score_result.evidence_count >= 1
    assert cluster_result.refined_event_count >= 1
    assert digest_result.digest_path is not None


def test_fetch_stage_fallback_uses_existing_raw_items(
    monkeypatch, hermetic_pipeline, pipeline_test_raw_items, tmp_path
) -> None:
    hermetic_pipeline.raw_items_path = tmp_path / "raw_items.json"
    write_json(hermetic_pipeline.raw_items_path, [item.model_dump() for item in pipeline_test_raw_items])
    monkeypatch.setattr(hermetic_pipeline.fetcher, "fetch_all", lambda _sources: ([], {"source_a": "no data"}))

    result = hermetic_pipeline.run_stage("fetch")

    # FetchStage preserves the existing file on empty fetches, but stage metrics
    # still reflect fetched records from this execution.
    assert result.fetched_count == 0
    persisted = hermetic_pipeline._load_raw_items_from_disk()
    assert len(persisted) == len(pipeline_test_raw_items)
