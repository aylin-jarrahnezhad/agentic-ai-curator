from pydantic import BaseModel, Field


class Diagnostics(BaseModel):
    fetch_totals: dict[str, int] = Field(default_factory=dict)
    fetch_error_type_counts: dict[str, int] = Field(default_factory=dict)
    fetch_zero_item_sources: list[str] = Field(default_factory=list)
    source_yield: dict[str, int] = Field(default_factory=dict)
    topic_yield: dict[str, int] = Field(default_factory=dict)
    dropped_items_summary: dict[str, int] = Field(default_factory=dict)
    cluster_counts: dict[str, int] = Field(default_factory=dict)
    score_distributions: dict[str, float] = Field(default_factory=dict)
    connector_failures: dict[str, str] = Field(default_factory=dict)
    pipeline_stage_counts: dict[str, int] = Field(default_factory=dict)
