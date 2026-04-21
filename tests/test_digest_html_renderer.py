from services.digest.digest_html_renderer import DigestHtmlRenderer


def test_digest_html_source_filters_and_data_attributes():
    html = DigestHtmlRenderer.render(
        "Weekly",
        "2026-04-02",
        "7d",
        [
            {
                "title": "Cluster A",
                "summary": "Summary text here.",
                "links": ["https://example.com/a"],
                "earliest_published_date": "2026-04-01",
                "source_ids": ["bbc_technology", "aws_ml_blog"],
                "score": {
                    "mean_relevance": 0.9,
                    "mean_importance": 0.8,
                    "mean_novelty": 0.7,
                    "mean_trust": 0.8,
                    "mean_composed": 0.85,
                },
            }
        ],
    )
    assert 'class="source-filter"' in html
    assert "bbc_technology" in html
    assert "aws ml blog" in html  # label formatting
    assert 'data-sources="aws_ml_blog bbc_technology"' in html
    assert 'id="digest-search-index"' in html
    assert '"titles"' in html and '"summaries"' in html
    assert 'id="search_q"' in html
    assert 'data-card-idx="0"' in html
    assert 'id="search_form"' in html
    assert 'id="search_btn"' in html


def test_load_registry_by_id_handles_invalid_payload(monkeypatch):
    import services.digest.digest_html_renderer as renderer_module

    monkeypatch.setattr(renderer_module, "read_json", lambda _path: {"sources": "bad"})
    assert DigestHtmlRenderer._load_registry_by_id() == {}


def test_load_registry_by_id_handles_read_error(monkeypatch):
    import services.digest.digest_html_renderer as renderer_module

    def _raise(_path):
        raise RuntimeError("boom")

    monkeypatch.setattr(renderer_module, "read_json", _raise)
    assert DigestHtmlRenderer._load_registry_by_id() == {}
