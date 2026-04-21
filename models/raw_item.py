from typing import Self

from pydantic import BaseModel, Field, model_validator

from utils.dates import parse_date, to_iso_date_utc, to_iso_datetime_utc

# Feedparser duplicates publication time under these keys; RawItem uses `published_at` only.
_PAYLOAD_DATE_KEY_ALIASES = frozenset(
    {
        "published",
        "updated",
        "published_parsed",
        "updated_parsed",
    }
)


class RawItem(BaseModel):
    id: str
    source_id: str
    connector: str
    title: str = ""
    summary: str = ""
    links: list[str] = Field(default_factory=list)
    url: str = ""
    published_at: str | None = None
    published_date: str | None = None
    author: str | None = None
    payload: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _normalize_payload_publication_keys(self) -> Self:
        """Drop feedparser date aliases from payload so dates use the same name as the model: `published_at`."""
        if not self.payload:
            return self
        self.payload = {k: v for k, v in self.payload.items() if k not in _PAYLOAD_DATE_KEY_ALIASES}
        return self

    @model_validator(mode="after")
    def _normalize_published_fields(self) -> Self:
        """Store ``published_at`` as UTC ISO with Z suffix and ``published_date`` as UTC ``YYYY-MM-DD``."""
        raw = self.published_at
        if not raw or not str(raw).strip():
            self.published_at = None
            self.published_date = None
            return self
        dt = parse_date(str(raw))
        if dt is None:
            self.published_at = None
            self.published_date = None
            return self
        self.published_at = to_iso_datetime_utc(dt)
        self.published_date = to_iso_date_utc(dt)
        return self
