from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC
from pathlib import Path
from typing import Any

from config.settings import (
    BATCH_SIZE_FOR_SCORING,
    INTERMEDIATE_DIR,
    SOURCE_REGISTRY_PATH,
    WEEKLY_WINDOW_DAYS,
)
from core.orchestrator import PipelineResult
from core.stages.cluster_stage import ClusterStage
from core.stages.digest_stage import DigestStage
from core.stages.fetch_stage import FetchStage
from core.stages.score_stage import ScoreStage
from crews.digest_crew import DigestCrew
from models.cluster_candidate import ClusterCandidate
from models.crew_contracts import EvidenceScoreResponse
from models.diagnostics import Diagnostics
from models.event import Event
from models.evidence_card import EvidenceCard
from models.normalized_item import NormalizedItem
from models.pipeline_types import ClusterRow, SourceConfig
from models.raw_item import RawItem
from models.scored_item import ScoreBundle, ScoredItem
from services.clustering.cluster_refinement_service import ClusterRefinementService
from services.clustering.coarse_clusterer import CoarseClusterer
from services.clustering.embedding_service import EmbeddingService
from services.digest.diagnostics_service import DiagnosticsService
from services.digest.digest_composer import DigestComposer
from services.fetch.source_fetch_service import SourceFetchService
from services.preprocess.deduplication_service import DeduplicationService
from services.preprocess.evidence_builder import EvidenceBuilder
from services.preprocess.normalizer import Normalizer
from services.scoring.event_dossier_builder import EventDossierBuilder
from services.scoring.event_scoring_service import EventScoringService
from services.scoring.heuristic_scoring_service import HeuristicScoringService
from services.scoring.semantic_scoring_service import SemanticScoringService
from services.storage.output_store import create_output_store
from utils.dates import in_last_days, to_iso_datetime_utc
from utils.json_utils import read_json, write_json
from utils.metrics import metrics
from utils.text import canonicalize_url, is_digest_worthy_content, is_useful_article_url

StageRunner = Callable[[], PipelineResult]


class WeeklyDigestPipeline:
    RELEVANCE_THRESHOLD_FOR_CLUSTERING = 0.5
    SCORING_PARALLEL_WORKERS = 2

    def __init__(self) -> None:
        self.fetcher = SourceFetchService()
        self.normalizer = Normalizer()
        self.dedupe = DeduplicationService()
        self.evidence_builder = EvidenceBuilder()
        self.light_scoring = HeuristicScoringService()
        self.embedding_service = EmbeddingService()
        self.coarse_clusterer = CoarseClusterer()
        self.crew = DigestCrew(Path("config/agents.yaml"), Path("config/tasks.yaml"))
        self.cluster_refiner = ClusterRefinementService(self.crew)
        self.dossier_builder = EventDossierBuilder()
        self.event_scorer = EventScoringService()
        self.semantic_scorer = SemanticScoringService(
            crew=self.crew,
            batch_size=BATCH_SIZE_FOR_SCORING,
            workers=self.SCORING_PARALLEL_WORKERS,
            build_scored_item=self._build_scored_item,
        )
        self.diagnostics_service = DiagnosticsService()
        self.digest_composer = DigestComposer(self.crew)
        self.output_store = create_output_store()
        self.raw_items_path = INTERMEDIATE_DIR / "raw_items.json"
        self.scored_items_path = INTERMEDIATE_DIR / "scored_items.json"
        self.clustered_items_path = INTERMEDIATE_DIR / "clustered_items.json"

    def run_stage(self, stage: str) -> PipelineResult:
        normalized_stage = stage.lower()
        runners: dict[str, StageRunner] = {
            "fetch": self._run_fetch_stage,
            "score": self._run_score_stage,
            "cluster": self._run_cluster_stage,
            "digest": self._run_digest_stage,
        }
        runner = runners.get(normalized_stage)
        if runner is None:
            raise ValueError(f"Unsupported stage '{stage}'. Expected one of: fetch, score, cluster, digest.")
        started = time.perf_counter()
        result = runner()
        metrics.observe("pipeline.stage_seconds", time.perf_counter() - started, stage=normalized_stage)
        return result

    def _run_fetch_stage(self) -> PipelineResult:
        return FetchStage(
            fetch_service=self.fetcher,
            raw_items_path=self.raw_items_path,
            base_item_builder=self._base_item,
        ).run()

    def _run_score_stage(self) -> PipelineResult:
        return ScoreStage(
            normalizer=self.normalizer,
            dedupe_service=self.dedupe,
            evidence_builder=self.evidence_builder,
            heuristic_scoring_service=self.light_scoring,
            raw_items_loader=self._load_raw_items_from_disk,
            scored_items_path=self.scored_items_path,
            semantic_scoring_service=self.semantic_scorer,
        ).run()

    def _run_cluster_stage(self) -> PipelineResult:
        return ClusterStage(
            normalizer=self.normalizer,
            dedupe_service=self.dedupe,
            evidence_builder=self.evidence_builder,
            heuristic_scoring_service=self.light_scoring,
            coarse_clusterer=self.coarse_clusterer,
            embedding_service=self.embedding_service,
            cluster_refiner=self.cluster_refiner,
            raw_items_loader=self._load_raw_items_from_disk,
            scored_items_path=self.scored_items_path,
            clustered_items_path=self.clustered_items_path,
            cluster_row_builder=self._cluster_row,
        ).run()

    def _run_digest_stage(self) -> PipelineResult:
        if self.raw_items_path.exists() and self.scored_items_path.exists():
            _, source_map = self._load_sources()
            raw_items = self._load_raw_items_from_disk()
            scored_items = self._load_scored_items_from_disk()
            normalized, deduped_count = self._normalize_and_dedupe(raw_items, source_map)
            cards = self._build_heuristic_cards(normalized)
            refined_clusters = self._load_refined_clusters_from_clustered_items()
            allowed_ids = {item_id for cluster in refined_clusters for item_id in cluster.item_ids}
            cards_for_events = [card for card in cards if card.id in allowed_ids]
            events = self._build_events(refined_clusters, cards_for_events, scored_items)
            diagnostics = self._build_diagnostics(
                raw_items=raw_items,
                normalized=normalized,
                cards=cards_for_events,
                scored_items=scored_items,
                refined_clusters=refined_clusters,
                events=events,
                failures={},
                deduped_count=deduped_count,
            )
            render_result = DigestStage(
                digest_composer=self.digest_composer,
                clustered_items_path=self.clustered_items_path,
                embedding_service=self.embedding_service,
                output_store=self.output_store,
                events=events,
                diagnostics=diagnostics,
                diagnostics_renderer=self.diagnostics_service.to_markdown,
            ).run()
            return PipelineResult(
                fetched_count=len(raw_items),
                normalized_count=len(normalized),
                evidence_count=len(cards_for_events),
                refined_event_count=len(events),
                digest_path=render_result.digest_path,
                diagnostics_path=render_result.diagnostics_path,
                scored_items=scored_items,
                events=events,
            )

        return DigestStage(
            digest_composer=self.digest_composer,
            clustered_items_path=self.clustered_items_path,
            embedding_service=self.embedding_service,
            output_store=self.output_store,
        ).run()

    def run(self) -> PipelineResult:
        run_started = time.perf_counter()
        sources, source_map = self._load_sources()
        raw_items, failures = self._fetch_raw_items_with_fallback(sources)
        normalized, deduped_count = self._normalize_and_dedupe(raw_items, source_map)
        cards = self._build_heuristic_cards(normalized)
        scored_items = self._score_cards(cards)
        refined_clusters, cards_for_events = self._cluster_cards(scored_items, cards)
        events = self._build_events(refined_clusters, cards_for_events, scored_items)
        diagnostics = self._build_diagnostics(
            raw_items=raw_items,
            normalized=normalized,
            cards=cards_for_events,
            scored_items=scored_items,
            refined_clusters=refined_clusters,
            events=events,
            failures=failures,
            deduped_count=deduped_count,
        )
        digest_path, diagnostics_path = self._render_outputs(events, diagnostics)
        metrics.observe("pipeline.run_seconds", time.perf_counter() - run_started, stage="all")
        return PipelineResult(
            fetched_count=len(raw_items),
            normalized_count=len(normalized),
            evidence_count=len(cards_for_events),
            refined_event_count=len(events),
            digest_path=digest_path,
            diagnostics_path=diagnostics_path,
            scored_items=scored_items,
            events=events,
        )

    @staticmethod
    def _load_sources() -> tuple[list[SourceConfig], dict[str, SourceConfig]]:
        payload = read_json(SOURCE_REGISTRY_PATH)
        source_items = payload.get("sources") if isinstance(payload, dict) else None
        if not isinstance(source_items, list):
            raise ValueError(f"Invalid source registry format at {SOURCE_REGISTRY_PATH}")
        sources: list[SourceConfig] = []
        for source in source_items:
            if not isinstance(source, dict):
                continue
            source_id = source.get("source_id")
            connector = source.get("connector")
            if not isinstance(source_id, str) or not source_id:
                continue
            if not isinstance(connector, str) or not connector:
                continue
            sources.append(source)
        source_map = {source["source_id"]: source for source in sources}
        return sources, source_map

    def _fetch_raw_items_with_fallback(self, sources: list[SourceConfig]) -> tuple[list[RawItem], dict[str, str]]:
        fetch_started = time.perf_counter()
        raw_items, failures = self.fetcher.fetch_all(sources)
        source_stats: list[dict[str, Any]] | None = None
        get_stats = getattr(self.fetcher, "get_last_fetch_stats", None)
        if callable(get_stats):
            stats_payload = get_stats()
            if isinstance(stats_payload, list):
                source_stats = [row for row in stats_payload if isinstance(row, dict)]
        metrics.observe("pipeline.stage_seconds", time.perf_counter() - fetch_started, stage="fetch")
        wrote_raw = write_json(
            self.raw_items_path,
            [self._base_item(item.id, item.title, item.summary, item.links, item.model_dump()) for item in raw_items],
            preserve_if_empty_would_erase=True,
        )
        report = FetchStage._build_fetch_report(
            sources=sources,
            raw_items=raw_items,
            failures=failures,
            source_stats=source_stats,
        )
        write_json(INTERMEDIATE_DIR / "fetch_report.json", report)
        (INTERMEDIATE_DIR / "fetch_report_summary.md").write_text(
            FetchStage._build_fetch_summary_markdown(report),
            encoding="utf-8",
        )
        if not raw_items and not wrote_raw:
            return self._load_raw_items_from_disk(), failures
        return raw_items, failures

    def _normalize_and_dedupe(
        self,
        raw_items: list[RawItem],
        source_map: dict[str, SourceConfig],
    ) -> tuple[list[NormalizedItem], int]:
        preprocess_started = time.perf_counter()
        normalized = [
            item
            for item in self.normalizer.normalize(raw_items, source_map)
            if in_last_days(item.published_at, WEEKLY_WINDOW_DAYS)
        ]
        normalized, deduped_count = self.dedupe.dedupe(normalized)
        metrics.observe("pipeline.stage_seconds", time.perf_counter() - preprocess_started, stage="preprocess")
        return normalized, deduped_count

    def _build_heuristic_cards(self, normalized: list[NormalizedItem]) -> list[EvidenceCard]:
        scoring_prep_started = time.perf_counter()
        cards = self.light_scoring.apply(self.evidence_builder.build(normalized))
        cards = [card for card in cards if is_digest_worthy_content(card.title, card.cleaned_excerpt or card.summary)]
        metrics.observe(
            "pipeline.stage_seconds",
            time.perf_counter() - scoring_prep_started,
            stage="heuristic_scoring",
        )
        return cards

    def _score_cards(self, cards: list[EvidenceCard]) -> list[ScoredItem]:
        semantic_scoring_started = time.perf_counter()
        scored_items = self.semantic_scorer.score(cards)
        metrics.observe(
            "pipeline.stage_seconds",
            time.perf_counter() - semantic_scoring_started,
            stage="semantic_scoring",
        )
        write_json(
            self.scored_items_path,
            [item.model_dump() for item in scored_items],
            preserve_if_empty_would_erase=True,
        )
        return scored_items

    def _cluster_cards(
        self,
        scored_items: list[ScoredItem],
        cards: list[EvidenceCard],
    ) -> tuple[list[ClusterCandidate], list[EvidenceCard]]:
        clustering_started = time.perf_counter()
        allowed_ids = {
            item.id for item in scored_items if item.scores.relevance >= self.RELEVANCE_THRESHOLD_FOR_CLUSTERING
        }
        cards = [card for card in cards if card.id in allowed_ids]
        refined_clusters, _ = self.cluster_refiner.refine(
            self.coarse_clusterer.cluster(cards, self.embedding_service.embed(cards))
        )
        cards_by_id = {card.id: card for card in cards}
        item_scores = {item.id: item for item in scored_items}
        cluster_rows: list[ClusterRow] = [
            self._cluster_row(cluster, cards_by_id, item_scores) for cluster in refined_clusters
        ]
        cluster_rows = sorted(
            cluster_rows,
            key=lambda row: (row["score"]["mean_composed"], row["score"]["mean_trust"]),
            reverse=True,
        )
        for idx, row in enumerate(cluster_rows, start=1):
            row["cluster_number"] = idx
        metrics.observe("pipeline.stage_seconds", time.perf_counter() - clustering_started, stage="clustering")
        write_json(
            self.clustered_items_path,
            cluster_rows,
            preserve_if_empty_would_erase=True,
        )
        return refined_clusters, cards

    def _build_events(
        self,
        refined_clusters: list[ClusterCandidate],
        cards: list[EvidenceCard],
        scored_items: list[ScoredItem],
    ) -> list[Event]:
        cards_by_id = {card.id: card for card in cards}
        item_scores = {item.id: item for item in scored_items}
        dossiers = self.dossier_builder.build(refined_clusters, cards_by_id)
        summary_items = self.crew.summarize_event_dossiers([dossier.model_dump(mode="json") for dossier in dossiers])
        summary_map = {summary.event_id: summary for summary in summary_items}
        return sorted(
            self.event_scorer.score_events(dossiers, item_scores, summary_map),
            key=lambda event: event.score.mean_composed,
            reverse=True,
        )

    def _build_diagnostics(
        self,
        *,
        raw_items: list[RawItem],
        normalized: list[NormalizedItem],
        cards: list[EvidenceCard],
        scored_items: list[ScoredItem],
        refined_clusters: list[ClusterCandidate],
        events: list[Event],
        failures: dict[str, str],
        deduped_count: int,
    ) -> Diagnostics:
        fetch_report = self._load_fetch_report()
        return self.diagnostics_service.build(
            normalized,
            cards,
            events,
            failures,
            {
                "raw_items": len(raw_items),
                "normalized_items": len(normalized),
                "evidence_cards": len(cards),
                "scored_items": len(scored_items),
                "refined_clusters": len(refined_clusters),
                "events": len(events),
            },
            {"dedupe_dropped": deduped_count},
            fetch_report=fetch_report,
        )

    def _render_outputs(self, events: list[Event], diagnostics: Diagnostics) -> tuple[str, str]:
        digest_started = time.perf_counter()
        render_result = DigestStage(
            digest_composer=self.digest_composer,
            clustered_items_path=self.clustered_items_path,
            embedding_service=self.embedding_service,
            output_store=self.output_store,
            events=events,
            diagnostics=diagnostics,
            diagnostics_renderer=self.diagnostics_service.to_markdown,
        ).run()
        metrics.observe("pipeline.stage_seconds", time.perf_counter() - digest_started, stage="digest_render")
        if render_result.digest_path is None or render_result.diagnostics_path is None:
            raise RuntimeError("Digest render stage did not produce expected output paths.")
        return render_result.digest_path, render_result.diagnostics_path

    def _load_raw_items_from_disk(self) -> list[RawItem]:
        if not self.raw_items_path.exists():
            raise FileNotFoundError(f"Missing required input file: {self.raw_items_path}")
        payload = read_json(self.raw_items_path)
        if not isinstance(payload, list):
            raise ValueError(f"Raw item payload must be a list in {self.raw_items_path}")
        return [RawItem.model_validate(item) for item in payload]

    def _load_scored_items_from_disk(self) -> list[ScoredItem]:
        if not self.scored_items_path.exists():
            raise FileNotFoundError(f"Missing required input file: {self.scored_items_path}")
        payload = read_json(self.scored_items_path)
        if not isinstance(payload, list):
            raise ValueError(f"Scored item payload must be a list in {self.scored_items_path}")
        return [ScoredItem.model_validate(item) for item in payload]

    def _load_refined_clusters_from_clustered_items(self) -> list[ClusterCandidate]:
        payload = read_json(self.clustered_items_path)
        if not isinstance(payload, list):
            raise ValueError(f"Clustered item payload must be a list in {self.clustered_items_path}")
        clusters: list[ClusterCandidate] = []
        for idx, row in enumerate(payload):
            if not isinstance(row, dict):
                continue
            item_ids = row.get("item_ids")
            links = row.get("links")
            if not isinstance(item_ids, list):
                continue
            clusters.append(
                ClusterCandidate(
                    cluster_id=str(row.get("cluster_number") or idx + 1),
                    item_ids=[str(item_id) for item_id in item_ids],
                    title=str(row.get("title") or ""),
                    summary=str(row.get("summary") or ""),
                    links=[str(link) for link in links] if isinstance(links, list) else [],
                )
            )
        return clusters

    @staticmethod
    def _load_fetch_report() -> dict[str, Any] | None:
        report_path = INTERMEDIATE_DIR / "fetch_report.json"
        if not report_path.exists():
            return None
        payload = read_json(report_path)
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _base_item(item_id: str, title: str, summary: str, links: list[str], full: dict) -> dict:
        payload = {"id": item_id, "title": title, "summary": summary, "links": links}
        payload.update(full)
        return payload

    @staticmethod
    def _cluster_earliest_date(item_ids: list[str], cards_by_id: dict[str, EvidenceCard]) -> str | None:
        dates: list[str] = []
        for item_id in item_ids:
            if item_id not in cards_by_id:
                continue
            card = cards_by_id[item_id]
            if card.published_date:
                dates.append(card.published_date)
            elif card.published_at is not None:
                dates.append(card.published_at.astimezone(UTC).date().isoformat())
        return min(dates) if dates else None

    @staticmethod
    def _safe_mean(values: list[float]) -> float:
        return round(sum(values) / len(values), 4) if values else 0.0

    def _cluster_row(
        self,
        cluster: ClusterCandidate,
        cards_by_id: dict[str, EvidenceCard],
        item_scores: dict[str, ScoredItem],
    ) -> ClusterRow:
        cluster_scores = [item_scores[item_id].scores for item_id in cluster.item_ids if item_id in item_scores]
        links = [canonicalize_url(link) for link in cluster.links]
        links = [link for link in links if link and is_useful_article_url(link)]
        links = list(dict.fromkeys(links))
        source_ids = sorted({cards_by_id[item_id].source_id for item_id in cluster.item_ids if item_id in cards_by_id})
        return {
            "title": cluster.title,
            "summary": cluster.summary,
            "links": links,
            "earliest_published_date": self._cluster_earliest_date(cluster.item_ids, cards_by_id),
            "item_ids": cluster.item_ids,
            "source_ids": source_ids,
            "score": {
                "mean_relevance": self._safe_mean([score.relevance for score in cluster_scores]),
                "mean_importance": self._safe_mean([score.importance for score in cluster_scores]),
                "mean_novelty": self._safe_mean([score.novelty for score in cluster_scores]),
                "mean_trust": self._safe_mean([score.trust for score in cluster_scores]),
                "mean_composed": self._safe_mean([score.composed for score in cluster_scores]),
            },
        }

    @staticmethod
    def _build_scored_item(
        card: EvidenceCard,
        scored_payload: EvidenceScoreResponse | dict[str, Any] | None,
    ) -> ScoredItem | None:
        if scored_payload is None:
            return None
        payload = (
            scored_payload
            if isinstance(scored_payload, EvidenceScoreResponse)
            else EvidenceScoreResponse.model_validate(scored_payload)
        )
        relevance = round(float(payload.semantic_relevance_score), 4)
        importance = round(float(payload.semantic_importance_score), 4)
        novelty = round(float(payload.semantic_novelty_score), 4)
        trust = round(max(0.0, min(1.0, float(card.trust_tier) / 5.0)), 4)
        composed = round(0.35 * relevance + 0.30 * importance + 0.20 * novelty + 0.15 * trust, 4)
        return ScoredItem(
            id=card.id,
            title=card.title,
            summary=card.cleaned_excerpt,
            links=card.links,
            published_at=to_iso_datetime_utc(card.published_at),
            published_date=card.published_date,
            scores=ScoreBundle(
                relevance=relevance,
                importance=importance,
                novelty=novelty,
                trust=trust,
                composed=composed,
            ),
            rationale=payload.rationale or "",
            scoring_source=payload.scoring_source,
        )
