from datetime import datetime

from pydantic import BaseModel, Field


class NormalizedItem(BaseModel):
    id: str
    source_id: str
    source_type: str
    category: str
    trust_tier: int
    title: str
    summary: str
    links: list[str] = Field(default_factory=list)
    canonical_url: str
    published_at: datetime | None = None
    published_date: str | None = None
    author: str | None = None
    language: str | None = "en"
