from __future__ import annotations

from dataclasses import dataclass

from models.event import Event
from models.scored_item import ScoredItem


@dataclass(slots=True)
class PipelineResult:
    fetched_count: int
    normalized_count: int
    evidence_count: int
    refined_event_count: int
    digest_path: str | None
    diagnostics_path: str | None
    scored_items: list[ScoredItem]
    events: list[Event]
