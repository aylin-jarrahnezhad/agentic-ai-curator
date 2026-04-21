from __future__ import annotations

from pathlib import Path

from core.stages.cluster_stage import ClusterStage
from core.stages.digest_stage import DigestStage
from core.stages.fetch_stage import FetchStage
from core.stages.score_stage import ScoreStage
from models.cluster_candidate import ClusterCandidate
from models.evidence_card import EvidenceCard
from models.normalized_item import NormalizedItem
from models.raw_item import RawItem
from models.scored_item import ScoreBundle, ScoredItem
from services.storage.output_store import LocalOutputStore
from utils.dates import utc_now
from utils.json_utils import read_json, write_json


def _raw_item(item_id: str) -> RawItem:
    now_iso = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
    return RawItem(
        id=item_id,
        source_id="source_a",
        connector="rss",
        title=f"title-{item_id}",
        summary="summary",
        links=[f"https://example.com/{item_id}"],
        url=f"https://example.com/{item_id}",
        published_at=now_iso,
        payload={},
    )


def _normalized(item_id: str) -> NormalizedItem:
    now = utc_now()
    return NormalizedItem(
        id=item_id,
        source_id="source_a",
        source_type="primary",
        category="company",
        trust_tier=5,
        title=f"title-{item_id}",
        summary="summary",
        links=[f"https://example.com/{item_id}"],
        canonical_url=f"https://example.com/{item_id}",
        published_at=now,
        published_date=now.strftime("%Y-%m-%d"),
    )


def _card(item_id: str) -> EvidenceCard:
    return EvidenceCard(
        id=item_id,
        source_id="source_a",
        title=f"title-{item_id}",
        summary="summary",
        links=[f"https://example.com/{item_id}"],
        canonical_url=f"https://example.com/{item_id}",
        source_type="primary",
        trust_tier=5,
        category="company",
        cleaned_excerpt="clean summary",
        possible_event_type="launch",
    )


def test_fetch_stage_writes_outputs(monkeypatch, tmp_path: Path) -> None:
    source_registry = tmp_path / "source_registry.json"
    write_json(source_registry, {"sources": [{"source_id": "source_a", "connector": "rss"}]})

    class Fetcher:
        @staticmethod
        def fetch_all(_sources):
            return [_raw_item("a1"), _raw_item("a2")], {"source_b": "timeout"}

    import core.stages.fetch_stage as fetch_stage_module

    monkeypatch.setattr(fetch_stage_module, "SOURCE_REGISTRY_PATH", source_registry)
    monkeypatch.setattr(fetch_stage_module, "INTERMEDIATE_DIR", tmp_path / "intermediate")

    stage = FetchStage(
        fetch_service=Fetcher(),
        raw_items_path=tmp_path / "raw_items.json",
        base_item_builder=lambda item_id, title, summary, links, full: {
            "id": item_id,
            "title": title,
            "summary": summary,
            "links": links,
            **full,
        },
    )
    result = stage.run()

    assert result.fetched_count == 2
    report_payload = read_json(tmp_path / "intermediate" / "fetch_report.json")
    assert isinstance(report_payload, dict)
    assert report_payload["totals"]["sources_failed"] == 1
    summary_markdown = (tmp_path / "intermediate" / "fetch_report_summary.md").read_text(encoding="utf-8")
    assert "Failure Details" in summary_markdown
    assert "source_b" in summary_markdown
    raw_payload = read_json(tmp_path / "raw_items.json")
    assert isinstance(raw_payload, list)
    assert len(raw_payload) == 2


def test_score_stage_scores_and_writes_output(monkeypatch, tmp_path: Path) -> None:
    source_registry = tmp_path / "source_registry.json"
    write_json(source_registry, {"sources": [{"source_id": "source_a", "connector": "rss"}]})

    class Normalizer:
        @staticmethod
        def normalize(_raw, _source_map):
            return [_normalized("a1"), _normalized("a2")]

    class Dedupe:
        @staticmethod
        def dedupe(items):
            return items, 0

    class EvidenceBuilder:
        @staticmethod
        def build(_items):
            return [_card("a1"), _card("a2")]

    class Heuristic:
        @staticmethod
        def apply(cards):
            return cards

    class Semantic:
        @staticmethod
        def score(cards):
            return [
                ScoredItem(
                    id=card.id,
                    title=card.title,
                    summary=card.summary,
                    links=card.links,
                    scores=ScoreBundle(relevance=0.8, importance=0.7, novelty=0.6, trust=1.0, composed=0.78),
                    rationale="ok",
                )
                for card in cards
            ]

    import core.stages.score_stage as score_stage_module

    monkeypatch.setattr(score_stage_module, "SOURCE_REGISTRY_PATH", source_registry)

    stage = ScoreStage(
        normalizer=Normalizer(),
        dedupe_service=Dedupe(),
        evidence_builder=EvidenceBuilder(),
        heuristic_scoring_service=Heuristic(),
        raw_items_loader=lambda: [_raw_item("a1"), _raw_item("a2")],
        scored_items_path=tmp_path / "scored.json",
        semantic_scoring_service=Semantic(),
    )
    result = stage.run()

    assert result.normalized_count == 2
    assert result.evidence_count == 2
    scored_payload = read_json(tmp_path / "scored.json")
    assert isinstance(scored_payload, list)
    assert len(scored_payload) == 2


def test_cluster_stage_filters_by_relevance(monkeypatch, tmp_path: Path) -> None:
    source_registry = tmp_path / "source_registry.json"
    write_json(source_registry, {"sources": [{"source_id": "source_a", "connector": "rss"}]})
    write_json(
        tmp_path / "scored.json",
        [
            ScoredItem(
                id="a1",
                title="t1",
                summary="s1",
                links=["https://example.com/a1"],
                scores=ScoreBundle(relevance=0.9, importance=0.7, novelty=0.7, trust=1.0, composed=0.82),
            ).model_dump(),
            ScoredItem(
                id="a2",
                title="t2",
                summary="s2",
                links=["https://example.com/a2"],
                scores=ScoreBundle(relevance=0.2, importance=0.5, novelty=0.5, trust=1.0, composed=0.48),
            ).model_dump(),
        ],
    )

    class Normalizer:
        @staticmethod
        def normalize(_raw, _source_map):
            return [_normalized("a1"), _normalized("a2")]

    class Dedupe:
        @staticmethod
        def dedupe(items):
            return items, 0

    class EvidenceBuilder:
        @staticmethod
        def build(_items):
            return [_card("a1"), _card("a2")]

    class Heuristic:
        @staticmethod
        def apply(cards):
            return cards

    class Coarse:
        @staticmethod
        def cluster(cards, _embeddings):
            return [
                ClusterCandidate(
                    cluster_id="c1",
                    item_ids=[card.id for card in cards],
                    title="C",
                    summary="S",
                    links=[],
                )
            ]

    class Embedding:
        @staticmethod
        def embed(cards):
            return [[1.0] * 8 for _ in cards]

    class Refiner:
        @staticmethod
        def refine(clusters):
            return clusters, {}

    import core.stages.cluster_stage as cluster_stage_module

    monkeypatch.setattr(cluster_stage_module, "SOURCE_REGISTRY_PATH", source_registry)

    stage = ClusterStage(
        normalizer=Normalizer(),
        dedupe_service=Dedupe(),
        evidence_builder=EvidenceBuilder(),
        heuristic_scoring_service=Heuristic(),
        coarse_clusterer=Coarse(),
        embedding_service=Embedding(),
        cluster_refiner=Refiner(),
        raw_items_loader=lambda: [_raw_item("a1"), _raw_item("a2")],
        scored_items_path=tmp_path / "scored.json",
        clustered_items_path=tmp_path / "clustered.json",
        cluster_row_builder=lambda cluster, cards_by_id, item_scores: {
            "title": cluster.title,
            "summary": cluster.summary,
            "links": [],
            "earliest_published_date": "2026-01-01",
            "item_ids": cluster.item_ids,
            "source_ids": sorted({cards_by_id[item_id].source_id for item_id in cluster.item_ids}),
            "score": {
                "mean_relevance": sum(item_scores[item_id].scores.relevance for item_id in cluster.item_ids)
                / len(cluster.item_ids),
                "mean_importance": 0.0,
                "mean_novelty": 0.0,
                "mean_trust": 0.0,
                "mean_composed": 0.0,
            },
        },
    )
    result = stage.run()

    assert result.evidence_count == 1
    assert result.refined_event_count == 1
    clustered_payload = read_json(tmp_path / "clustered.json")
    assert isinstance(clustered_payload, list)
    assert clustered_payload[0]["cluster_number"] == 1


def test_digest_stage_renders_outputs(tmp_path: Path) -> None:
    class Composer:
        @staticmethod
        def to_markdown(report, events=None, clusters=None):  # noqa: ARG004
            return f"# {report.title}\n\nok"

    clustered_items = [
        {
            "title": "Cluster A",
            "summary": "A long summary that should be displayed.",
            "links": ["https://example.com/a1"],
            "earliest_published_date": "2026-01-01",
            "source_ids": ["source_a"],
            "score": {
                "mean_relevance": 0.8,
                "mean_importance": 0.7,
                "mean_novelty": 0.6,
                "mean_trust": 1.0,
                "mean_composed": 0.77,
            },
        }
    ]
    clustered_path = tmp_path / "clustered.json"
    write_json(clustered_path, clustered_items)

    stage = DigestStage(
        digest_composer=Composer(),
        clustered_items_path=clustered_path,
        output_store=LocalOutputStore(tmp_path / "outputs"),
    )
    result = stage.run()

    assert result.digest_path
    assert (tmp_path / "outputs" / "latest.html").exists()
