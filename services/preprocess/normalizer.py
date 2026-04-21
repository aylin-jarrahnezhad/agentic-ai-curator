from models.normalized_item import NormalizedItem
from models.raw_item import RawItem
from utils.dates import parse_date, to_iso_date_utc
from utils.text import canonicalize_url, clean_html_text, clean_text, is_useful_article_url


class Normalizer:
    def normalize(self, raw_items: list[RawItem], source_map: dict[str, dict]) -> list[NormalizedItem]:
        out: list[NormalizedItem] = []
        for raw in raw_items:
            source = source_map.get(raw.source_id)
            if source is None:
                continue
            title = clean_text(raw.title)
            summary = self._best_raw_summary(raw, title)
            normalized_links = [canonicalize_url(link) for link in raw.links]
            normalized_links = [link for link in normalized_links if link and is_useful_article_url(link)]
            primary = canonicalize_url(raw.url or "")
            if primary and is_useful_article_url(primary):
                links = list(dict.fromkeys([primary] + normalized_links))
            else:
                links = list(dict.fromkeys(normalized_links))
            if not links:
                continue
            canonical_url = links[0]
            pa = parse_date(raw.published_at)
            out.append(
                NormalizedItem(
                    id=raw.id,
                    source_id=raw.source_id,
                    source_type=source["source_type"],
                    category=source["category"],
                    trust_tier=source["trust_tier"],
                    title=title,
                    summary=summary,
                    links=links,
                    canonical_url=canonical_url,
                    published_at=pa,
                    published_date=to_iso_date_utc(pa),
                    author=raw.author,
                )
            )
        return out

    @staticmethod
    def _best_raw_summary(raw: RawItem, title: str) -> str:
        candidates: list[str] = [clean_text(raw.summary)]
        payload = raw.payload or {}
        for content_item in payload.get("content", []) or []:
            if isinstance(content_item, dict):
                candidates.append(clean_html_text(content_item.get("value", "")))
        summary_detail = payload.get("summary_detail", {}) or {}
        if isinstance(summary_detail, dict):
            candidates.append(clean_html_text(summary_detail.get("value", "")))
        payload_summary = payload.get("summary") or payload.get("description")
        if payload_summary:
            candidates.append(clean_html_text(payload_summary))
        candidates = [c for c in candidates if c]
        if not candidates:
            return title
        return max(candidates, key=len)
