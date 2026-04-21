from datetime import datetime

from pydantic import BaseModel, Field


class EventDossier(BaseModel):
    event_id: str
    title: str
    summary: str
    links: list[str] = Field(default_factory=list)
    item_ids: list[str] = Field(default_factory=list)
    primary_source_candidates: list[str] = Field(default_factory=list)
    secondary_source_candidates: list[str] = Field(default_factory=list)
    support_types: list[str] = Field(default_factory=list)
    merged_facts: list[str] = Field(default_factory=list)
    earliest_timestamp: datetime | None = None
    latest_timestamp: datetime | None = None
    topic_buckets: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    source_diversity: int = 0
