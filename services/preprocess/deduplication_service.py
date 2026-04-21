from difflib import SequenceMatcher

from models.normalized_item import NormalizedItem


class DeduplicationService:
    """Drop duplicate/near-duplicate normalized items."""

    def dedupe(self, items: list[NormalizedItem]) -> tuple[list[NormalizedItem], int]:
        seen_urls: set[str] = set()
        kept: list[NormalizedItem] = []
        dropped = 0
        for item in items:
            if item.canonical_url and item.canonical_url in seen_urls:
                dropped += 1
                continue
            is_near_duplicate_title = any(
                SequenceMatcher(None, item.title.lower(), existing.title.lower()).ratio() > 0.92
                for existing in kept[-40:]
            )
            if is_near_duplicate_title:
                dropped += 1
                continue
            if item.canonical_url:
                seen_urls.add(item.canonical_url)
            kept.append(item)
        return kept, dropped
