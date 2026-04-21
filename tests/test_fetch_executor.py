from services.fetch.source_fetch_service import SourceFetchService


def test_fetch_executor_unknown_connector():
    items, failures = SourceFetchService().fetch_all([{"source_id": "x", "connector": "unknown"}])
    assert items == []
    assert "x" in failures


def test_fetch_executor_unknown_connector_with_stats():
    items, failures, stats = SourceFetchService().fetch_all_with_stats([{"source_id": "x", "connector": "unknown"}])
    assert items == []
    assert "x" in failures
    assert stats[0]["source_id"] == "x"
    assert stats[0]["items_fetched"] == 0
    assert stats[0]["status"] == "failed"
