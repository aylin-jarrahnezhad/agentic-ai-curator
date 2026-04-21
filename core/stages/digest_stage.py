from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Callable, Protocol

from config.settings import WEEKLY_WINDOW_DAYS
from core.orchestrator import PipelineResult
from models.diagnostics import Diagnostics
from models.digest_report import DigestReport
from models.event import Event
from models.pipeline_types import ClusterRow
from services.clustering.embedding_service import EmbeddingService
from services.digest.digest_html_renderer import DigestHtmlRenderer
from services.storage.output_store import OutputStore, create_output_store
from utils.dates import utc_now
from utils.json_utils import read_json


class DigestComposerLike(Protocol):
    def compose(self, events: list[Event], diagnostics: Diagnostics, window: str) -> DigestReport: ...

    def to_markdown(self, report: DigestReport, events=None, clusters=None) -> str: ...


class DigestStage:
    def __init__(
        self,
        digest_composer: DigestComposerLike,
        clustered_items_path: Path,
        embedding_service: EmbeddingService | None = None,
        output_store: OutputStore | None = None,
        events: list[Event] | None = None,
        diagnostics: Diagnostics | None = None,
        diagnostics_renderer: Callable[[Diagnostics], str] | None = None,
    ) -> None:
        self.digest_composer = digest_composer
        self.clustered_items_path = clustered_items_path
        self.embedding_service = embedding_service
        self.output_store = output_store or create_output_store()
        self.events = events
        self.diagnostics = diagnostics
        self.diagnostics_renderer = diagnostics_renderer

    def run(self) -> PipelineResult:
        clusters = read_json(self.clustered_items_path)
        if not isinstance(clusters, list):
            raise ValueError(f"Clustered item payload must be a list in {self.clustered_items_path}")
        cluster_rows: list[ClusterRow] = [cluster for cluster in clusters if isinstance(cluster, dict)]
        now = utc_now()
        run_key = now.strftime("%Y_%m_%d")
        digest_name = f"weekly_digest_{run_key}.md"
        digest_html_name = f"weekly_digest_{run_key}.html"
        diagnostics_path: str | None = None
        if self.events is not None and self.diagnostics is not None:
            report = self.digest_composer.compose(
                self.events,
                self.diagnostics,
                f"{(now - timedelta(days=WEEKLY_WINDOW_DAYS)).date()} to {now.date()}",
            )
            markdown = self.digest_composer.to_markdown(report, events=self.events, clusters=cluster_rows)
            diagnostics_name = f"weekly_diagnostics_{run_key}.md"
            diagnostics_path = self.output_store.write_text(
                diagnostics_name,
                (
                    self.diagnostics_renderer(self.diagnostics)
                    if self.diagnostics_renderer is not None
                    else self.diagnostics.model_dump_json(indent=2)
                ),
            )
        else:
            report = DigestReport(
                title="Weekly AI/Data Digest",
                run_date=now.strftime("%Y-%m-%d"),
                time_window=f"{(now - timedelta(days=WEEKLY_WINDOW_DAYS)).date()} to {now.date()}",
                executive_summary="",
                top_developments="",
                research_highlights="",
                company_platform_moves="",
                ecosystem_themes="",
                methodology_note="",
            )
            markdown = self.digest_composer.to_markdown(report, clusters=cluster_rows)
        digest_path = self.output_store.write_text(
            digest_name,
            markdown,
        )
        digest_html = DigestHtmlRenderer.render(
            report.title,
            report.run_date,
            report.time_window,
            cluster_rows,
            embedding_service=self.embedding_service,
        )
        self.output_store.write_text(
            digest_html_name,
            digest_html,
        )
        self.output_store.write_text("latest.html", digest_html)
        return PipelineResult(
            fetched_count=0,
            normalized_count=0,
            evidence_count=0,
            refined_event_count=0,
            digest_path=digest_path,
            diagnostics_path=diagnostics_path,
            scored_items=[],
            events=[],
        )
