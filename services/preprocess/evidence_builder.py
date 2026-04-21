from models.evidence_card import EvidenceCard
from models.normalized_item import NormalizedItem
from services.preprocess.content_enricher import ContentEnricher


class EvidenceBuilder:
    def __init__(self) -> None:
        self.enricher = ContentEnricher()

    def build(self, items: list[NormalizedItem]) -> list[EvidenceCard]:
        cards: list[EvidenceCard] = []
        for item in items:
            enriched = self.enricher.enrich(item)
            cards.append(
                EvidenceCard(
                    id=item.id,
                    source_id=item.source_id,
                    title=item.title,
                    summary=item.summary,
                    links=item.links,
                    canonical_url=item.canonical_url,
                    published_at=item.published_at,
                    published_date=item.published_date,
                    source_type=item.source_type,
                    trust_tier=item.trust_tier,
                    category=item.category,
                    cleaned_excerpt=enriched["cleaned_excerpt"],
                    entities=enriched["entities"],
                    key_phrases=enriched["key_phrases"],
                    likely_topic_buckets=enriched["likely_topic_buckets"],
                    possible_event_type=enriched["possible_event_type"],
                    identifiers=enriched["identifiers"],
                    completeness_flag=enriched["completeness_flag"],
                    weak_relevance_score=enriched["weak_relevance_score"],
                )
            )
        return cards
