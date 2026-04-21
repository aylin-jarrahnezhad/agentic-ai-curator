from datetime import datetime

from pydantic import BaseModel, Field


class EventScore(BaseModel):
    mean_composed: float
    reliability_score: float
    importance_score: float
    novelty_score: float
    combined_score: float


class Event(BaseModel):
    event_id: str
    title: str
    summary: str
    links: list[str] = Field(default_factory=list)
    earliest_item_date: datetime | None = None
    item_ids: list[str] = Field(default_factory=list)
    why_it_matters: str = ""
    confidence_note: str = ""
    theme_label: str = ""
    score: EventScore
