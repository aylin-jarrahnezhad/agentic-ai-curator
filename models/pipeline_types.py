from __future__ import annotations

from typing import NotRequired, Required, TypedDict


class SourceConfig(TypedDict, total=False):
    source_id: Required[str]
    connector: Required[str]
    source_type: NotRequired[str]
    category: NotRequired[str]
    trust_tier: NotRequired[int]
    feed_url: NotRequired[str]
    url: NotRequired[str]
    api_endpoint: NotRequired[str]


class ClusterScore(TypedDict):
    mean_relevance: float
    mean_importance: float
    mean_novelty: float
    mean_trust: float
    mean_composed: float


class ClusterRow(TypedDict):
    title: str
    summary: str
    links: list[str]
    earliest_published_date: str | None
    item_ids: list[str]
    source_ids: list[str]
    score: ClusterScore
    cluster_number: NotRequired[int]
