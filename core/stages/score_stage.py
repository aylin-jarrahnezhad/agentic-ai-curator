from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from config.settings import SOURCE_REGISTRY_PATH, WEEKLY_WINDOW_DAYS
from core.orchestrator import PipelineResult
from models.evidence_card import EvidenceCard
from models.normalized_item import NormalizedItem
from models.pipeline_types import SourceConfig
from models.raw_item import RawItem
from models.scored_item import ScoredItem
from utils.dates import in_last_days
from utils.json_utils import read_json, write_json
from utils.text import is_digest_worthy_content


class NormalizerService(Protocol):
    def normalize(self, raw_items: list[RawItem], source_map: dict[str, SourceConfig]) -> list[NormalizedItem]: ...


class DeduplicationService(Protocol):
    def dedupe(self, normalized: list[NormalizedItem]) -> tuple[list[NormalizedItem], int]: ...


class EvidenceBuilderService(Protocol):
    def build(self, normalized: list[NormalizedItem]) -> list[EvidenceCard]: ...


class HeuristicScoringService(Protocol):
    def apply(self, cards: list[EvidenceCard]) -> list[EvidenceCard]: ...


class SemanticScoringService(Protocol):
    def score(self, cards: list[EvidenceCard]) -> list[ScoredItem]: ...


class ScoreStage:
    def __init__(
        self,
        normalizer: NormalizerService,
        dedupe_service: DeduplicationService,
        evidence_builder: EvidenceBuilderService,
        heuristic_scoring_service: HeuristicScoringService,
        raw_items_loader: Callable[[], list[RawItem]],
        scored_items_path: Path,
        semantic_scoring_service: SemanticScoringService,
    ) -> None:
        self.normalizer = normalizer
        self.dedupe_service = dedupe_service
        self.evidence_builder = evidence_builder
        self.heuristic_scoring_service = heuristic_scoring_service
        self.raw_items_loader = raw_items_loader
        self.scored_items_path = scored_items_path
        self.semantic_scoring_service = semantic_scoring_service

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
        source_map = self._load_source_map()
        normalized = [
            n
            for n in self.normalizer.normalize(raw_items, source_map)
            if in_last_days(n.published_at, WEEKLY_WINDOW_DAYS)
        ]
        normalized, _ = self.dedupe_service.dedupe(normalized)
        cards = self.heuristic_scoring_service.apply(self.evidence_builder.build(normalized))
        cards = [c for c in cards if is_digest_worthy_content(c.title, c.cleaned_excerpt or c.summary)]

        scored_items = self.semantic_scoring_service.score(cards)
        write_json(
            self.scored_items_path,
            [s.model_dump() for s in scored_items],
            preserve_if_empty_would_erase=True,
        )
        return PipelineResult(
            fetched_count=len(raw_items),
            normalized_count=len(normalized),
            evidence_count=len(cards),
            refined_event_count=0,
            digest_path=None,
            diagnostics_path=None,
            scored_items=scored_items,
            events=[],
        )
