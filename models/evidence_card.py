from datetime import datetime

from pydantic import BaseModel, Field


class EvidenceCard(BaseModel):
    id: str
    source_id: str
    title: str
    summary: str
    links: list[str] = Field(default_factory=list)
    canonical_url: str
    published_at: datetime | None = None
    published_date: str | None = None
    source_type: str
    trust_tier: int
    category: str
    cleaned_excerpt: str
    entities: list[str] = Field(default_factory=list)
    key_phrases: list[str] = Field(default_factory=list)
    likely_topic_buckets: list[str] = Field(default_factory=list)
    possible_event_type: str
    identifiers: dict[str, str] = Field(default_factory=dict)
    completeness_flag: bool = True
    freshness_score: float = 0.0
    source_trust_prior: float = 0.0
    completeness_score: float = 0.0
    weak_relevance_score: float = 0.0
