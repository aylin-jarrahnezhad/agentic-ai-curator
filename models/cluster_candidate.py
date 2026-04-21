from pydantic import BaseModel, Field


class ClusterCandidate(BaseModel):
    cluster_id: str
    item_ids: list[str] = Field(default_factory=list)
    title: str = ""
    summary: str = ""
    links: list[str] = Field(default_factory=list)
