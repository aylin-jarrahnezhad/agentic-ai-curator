from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EvidenceScoreRequest(BaseModel):
    id: str
    title: str = ""
    summary: str = ""
    cleaned_excerpt: str = ""
    category: str = ""


class EvidenceScoreResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    semantic_relevance_score: float
    semantic_importance_score: float
    semantic_novelty_score: float
    rationale: str = ""
    scoring_source: Literal["llm", "fallback"] = "llm"


class ClusterRefinementRequest(BaseModel):
    cluster_id: str
    item_ids: list[str] = Field(default_factory=list)
    title: str = ""
    summary: str = ""
    links: list[str] = Field(default_factory=list)


class ClusterRefinementResponse(BaseModel):
    cluster_mapping: dict[str, str] = Field(default_factory=dict)
    labels: dict[str, str] = Field(default_factory=dict)


class EventSummaryRequest(BaseModel):
    event_id: str
    title: str = ""
    summary: str = ""
    links: list[str] = Field(default_factory=list)
    item_ids: list[str] = Field(default_factory=list)
    primary_source_candidates: list[str] = Field(default_factory=list)
    secondary_source_candidates: list[str] = Field(default_factory=list)
    support_types: list[str] = Field(default_factory=list)
    merged_facts: list[str] = Field(default_factory=list)
    earliest_timestamp: str | None = None
    latest_timestamp: str | None = None
    topic_buckets: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    source_diversity: int = 0


class EventSummaryResponse(BaseModel):
    event_id: str
    title: str = ""
    summary: str = ""
    why_it_matters: str = ""
    confidence_note: str = ""
    theme_label: str = ""


class DigestSectionResponse(BaseModel):
    executive_summary: str
    top_developments: str = ""
    research_highlights: str = ""
    company_platform_moves: str = ""
    ecosystem_themes: str = ""
    methodology_note: str = ""
