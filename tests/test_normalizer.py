from models.raw_item import RawItem
from services.preprocess.normalizer import Normalizer


def test_raw_item_payload_strips_feedparser_date_aliases():
    r = RawItem(
        id="1",
        source_id="s",
        connector="rss",
        title="T",
        summary="S",
        links=["https://example.com/a"],
        url="https://example.com/a",
        published_at="2024-01-02T00:00:00+00:00",
        payload={
            "title": "T",
            "published": "Tue, 02 Jan 2024 00:00:00 GMT",
            "updated": "Wed, 03 Jan 2024 00:00:00 GMT",
            "published_parsed": None,
            "links": [],
            "id": "x",
        },
    )
    assert "published" not in r.payload
    assert "updated" not in r.payload
    assert "published_parsed" not in r.payload
    assert r.payload.get("title") == "T"
    assert r.published_at == "2024-01-02T00:00:00Z"
    assert r.published_date == "2024-01-02"


def test_normalizer_basic():
    raw = [
        RawItem(
            id="1",
            source_id="s",
            connector="rss",
            title=" T ",
            summary=" S ",
            links=["https://example.com/a"],
            url="https://example.com/a",
        )
    ]
    src = {"s": {"source_type": "primary", "category": "news", "trust_tier": 5}}
    out = Normalizer().normalize(raw, src)
    assert out[0].title == "T"
    assert out[0].canonical_url == "https://example.com/a"


def test_normalizer_drops_nav_only_urls():
    raw = [
        RawItem(
            id="bad",
            source_id="s",
            connector="html",
            title="About DeepMind",
            summary="Marketing",
            links=["https://deepmind.google/about"],
            url="https://deepmind.google/about",
        )
    ]
    src = {"s": {"source_type": "primary", "category": "news", "trust_tier": 5}}
    assert Normalizer().normalize(raw, src) == []
