def test_pipeline_smoke(monkeypatch, hermetic_pipeline, pipeline_test_raw_items):
    monkeypatch.setattr(
        hermetic_pipeline.fetcher,
        "fetch_all",
        lambda sources: (pipeline_test_raw_items, {}),
    )

    result = hermetic_pipeline.run()
    assert result.fetched_count == 2
    assert result.normalized_count >= 1
    assert result.evidence_count >= 1
    assert result.refined_event_count >= 1
    assert result.digest_path
    latest_html = hermetic_pipeline.output_store.read_bytes("latest.html")
    assert latest_html.startswith(b"<!doctype html>")
