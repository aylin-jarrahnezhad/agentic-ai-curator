import numpy as np
import pytest

import core.pipeline as pipeline_module
from core.pipeline import WeeklyDigestPipeline
from models.crew_contracts import (
    ClusterRefinementResponse,
    DigestSectionResponse,
    EventSummaryResponse,
    EvidenceScoreResponse,
)
from models.raw_item import RawItem
from services.storage.output_store import LocalOutputStore
from utils.dates import utc_now
from utils.json_utils import write_json


class DummyEmbeddingService:
    def embed(self, cards):
        if not cards:
            return np.zeros((0, 8), dtype=float)
        return np.ones((len(cards), 8), dtype=float)


class DummyCrew:
    def __init__(self, *args, **kwargs):  # noqa: ARG002
        pass

    @staticmethod
    def score_evidence_cards(cards: list[dict]) -> list[EvidenceScoreResponse]:
        return [
            EvidenceScoreResponse(
                id=(card["id"] if isinstance(card, dict) else card.id),
                semantic_relevance_score=0.9,
                semantic_importance_score=0.8,
                semantic_novelty_score=0.7,
                rationale="test scoring",
            )
            for card in cards
        ]

    @staticmethod
    def refine_clusters(clusters: list[dict]) -> ClusterRefinementResponse:
        mapping = {cluster["cluster_id"]: cluster["cluster_id"] for cluster in clusters}
        labels = {cluster["cluster_id"]: cluster.get("title", "") for cluster in clusters}
        return ClusterRefinementResponse(cluster_mapping=mapping, labels=labels)

    @staticmethod
    def summarize_event_dossiers(dossiers: list[dict]) -> list[EventSummaryResponse]:
        return [
            EventSummaryResponse(
                event_id=dossier["event_id"],
                title=dossier.get("title", "Test event"),
                summary=dossier.get("summary", "Test summary"),
                why_it_matters="Test significance",
                confidence_note="Deterministic test summary",
                theme_label="test_theme",
            )
            for dossier in dossiers
        ]

    @staticmethod
    def compose_digest(payload: dict) -> DigestSectionResponse:
        _ = payload
        return DigestSectionResponse(
            executive_summary="Test executive summary.",
            top_developments="- Test development",
            research_highlights="- Test research",
            company_platform_moves="- Test company move",
            ecosystem_themes="- Test theme",
            methodology_note="Test methodology note.",
        )


@pytest.fixture
def pipeline_test_raw_items() -> list[RawItem]:
    now_iso = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
    return [
        RawItem(
            id="a1",
            source_id="openai_blog",
            connector="rss",
            title="OpenAI ships a new model",
            summary="A major AI release with benchmarking details and deployment notes.",
            links=["https://example.com/a1"],
            url="https://example.com/a1",
            published_at=now_iso,
            payload={},
        ),
        RawItem(
            id="a2",
            source_id="openai_blog",
            connector="rss",
            title="Model deployment best practices",
            summary="Guidance for inference, monitoring, and operational reliability.",
            links=["https://example.com/a2"],
            url="https://example.com/a2",
            published_at=now_iso,
            payload={},
        ),
    ]


@pytest.fixture
def hermetic_pipeline(monkeypatch, tmp_path) -> WeeklyDigestPipeline:
    source_registry = tmp_path / "source_registry.json"
    write_json(
        source_registry,
        {
            "sources": [
                {
                    "source_id": "openai_blog",
                    "connector": "rss",
                    "source_type": "primary",
                    "category": "company",
                    "trust_tier": 5,
                }
            ]
        },
    )
    monkeypatch.setattr(pipeline_module, "SOURCE_REGISTRY_PATH", source_registry)
    monkeypatch.setattr(pipeline_module, "INTERMEDIATE_DIR", tmp_path / "intermediate")
    monkeypatch.setattr(pipeline_module, "EmbeddingService", DummyEmbeddingService)
    monkeypatch.setattr(pipeline_module, "DigestCrew", DummyCrew)

    pipeline = WeeklyDigestPipeline()
    pipeline.output_store = LocalOutputStore(tmp_path / "outputs")
    return pipeline
