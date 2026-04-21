from typing import Literal

from pydantic import BaseModel, Field


class ScoreBundle(BaseModel):
    relevance: float
    importance: float
    novelty: float
    trust: float
    composed: float


class ScoredItem(BaseModel):
    id: str
    title: str
    summary: str
    links: list[str] = Field(default_factory=list)
    published_at: str | None = None
    published_date: str | None = None
    scores: ScoreBundle
    rationale: str | None = None
    scoring_source: Literal["llm", "fallback"] = "llm"
