from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from config.settings import SOURCE_REGISTRY_PATH, WEEKLY_WINDOW_DAYS
from core.orchestrator import PipelineResult
from models.cluster_candidate import ClusterCandidate
from models.evidence_card import EvidenceCard
from models.normalized_item import NormalizedItem
from models.pipeline_types import ClusterRow, SourceConfig
from models.raw_item import RawItem
from models.scored_item import ScoredItem
from utils.dates import in_last_days
from utils.json_utils import read_json, write_json


class NormalizerService(Protocol):
    def normalize(self, raw_items: list[RawItem], source_map: dict[str, SourceConfig]) -> list[NormalizedItem]: ...


class DeduplicationService(Protocol):
    def dedupe(self, normalized: list[NormalizedItem]) -> tuple[list[NormalizedItem], int]: ...


class EvidenceBuilderService(Protocol):
    def build(self, normalized: list[NormalizedItem]) -> list[EvidenceCard]: ...


class HeuristicScoringService(Protocol):
    def apply(self, cards: list[EvidenceCard]) -> list[EvidenceCard]: ...


class CoarseClustererService(Protocol):
    def cluster(self, cards: list[EvidenceCard], embeddings) -> list[ClusterCandidate]: ...


class EmbeddingService(Protocol):
    def embed(self, cards: list[EvidenceCard]): ...


class ClusterRefinerService(Protocol):
    def refine(self, coarse_clusters: list[ClusterCandidate]) -> tuple[list[ClusterCandidate], dict[str, int]]: ...


class ClusterStage:
    RELEVANCE_THRESHOLD_FOR_CLUSTERING = 0.5

    def __init__(
        self,
        normalizer: NormalizerService,
        dedupe_service: DeduplicationService,
        evidence_builder: EvidenceBuilderService,
        heuristic_scoring_service: HeuristicScoringService,
        coarse_clusterer: CoarseClustererService,
        embedding_service: EmbeddingService,
        cluster_refiner: ClusterRefinerService,
        raw_items_loader: Callable[[], list[RawItem]],
        scored_items_path: Path,
        clustered_items_path: Path,
        cluster_row_builder: Callable[[ClusterCandidate, dict[str, EvidenceCard], dict[str, ScoredItem]], ClusterRow],
    ) -> None:
        self.normalizer = normalizer
        self.dedupe_service = dedupe_service
        self.evidence_builder = evidence_builder
        self.heuristic_scoring_service = heuristic_scoring_service
        self.coarse_clusterer = coarse_clusterer
        self.embedding_service = embedding_service
        self.cluster_refiner = cluster_refiner
        self.raw_items_loader = raw_items_loader
        self.scored_items_path = scored_items_path
        self.clustered_items_path = clustered_items_path
        self.cluster_row_builder = cluster_row_builder

    @staticmethod
    def _load_source_map() -> dict[str, SourceConfig]:
        payload = read_json(SOURCE_REGISTRY_PATH)
        sources = payload.get("sources") if isinstance(payload, dict) else None
        if not isinstance(sources, list):
            raise ValueError(f"Invalid source registry format at {SOURCE_REGISTRY_PATH}")
        out: dict[str, SourceConfig] = {}
        for source in sources:
            if not isinstance(source, dict):
                continue
            source_id = source.get("source_id")
            connector = source.get("connector")
            if not isinstance(source_id, str) or not source_id:
                continue
            if not isinstance(connector, str) or not connector:
                continue
            out[source_id] = source
        return out

    def run(self) -> PipelineResult:
        raw_items = self.raw_items_loader()
        scored_payload = read_json(self.scored_items_path)
        if not isinstance(scored_payload, list):
            raise ValueError(f"Scored item payload must be a list in {self.scored_items_path}")
        scored_items = [ScoredItem.model_validate(item) for item in scored_payload]
        allowed_ids = {s.id for s in scored_items if s.scores.relevance >= self.RELEVANCE_THRESHOLD_FOR_CLUSTERING}

        source_map = self._load_source_map()
        normalized = [
            n
            for n in self.normalizer.normalize(raw_items, source_map)
            if in_last_days(n.published_at, WEEKLY_WINDOW_DAYS)
        ]
        normalized, _ = self.dedupe_service.dedupe(normalized)
        cards = self.heuristic_scoring_service.apply(self.evidence_builder.build(normalized))
        cards = [c for c in cards if c.id in allowed_ids]

        refined_clusters, _ = self.cluster_refiner.refine(
            self.coarse_clusterer.cluster(cards, self.embedding_service.embed(cards))
        )
        cards_by_id = {c.id: c for c in cards}
        item_scores = {s.id: s for s in scored_items}
        cluster_rows = [self.cluster_row_builder(c, cards_by_id, item_scores) for c in refined_clusters]
        cluster_rows = sorted(
            cluster_rows,
            key=lambda x: (x["score"]["mean_composed"], x["score"]["mean_trust"]),
            reverse=True,
        )
        for idx, row in enumerate(cluster_rows, start=1):
            row["cluster_number"] = idx
        write_json(
            self.clustered_items_path,
            cluster_rows,
            preserve_if_empty_would_erase=True,
        )

        return PipelineResult(
            fetched_count=len(raw_items),
            normalized_count=len(normalized),
            evidence_count=len(cards),
            refined_event_count=len(refined_clusters),
            digest_path=None,
            diagnostics_path=None,
            scored_items=scored_items,
            events=[],
        )
