from config.settings import WEEKLY_WINDOW_DAYS
from models.evidence_card import EvidenceCard
from utils.dates import utc_now


class HeuristicScoringService:
    """Apply deterministic pre-scoring features to evidence cards."""

    def apply(self, cards: list[EvidenceCard]) -> list[EvidenceCard]:
        now = utc_now()
        for card in cards:
            if card.published_at is None:
                freshness = 0.4
            else:
                age = max(0.0, (now - card.published_at).total_seconds() / 86400)
                freshness = max(0.0, 1.0 - (age / WEEKLY_WINDOW_DAYS))
            card.freshness_score = round(freshness, 4)
            card.source_trust_prior = round(min(1.0, card.trust_tier / 5.0), 4)
            card.completeness_score = round(self._weighted_completeness(card), 4)
        return cards

    @staticmethod
    def _weighted_completeness(card: EvidenceCard) -> float:
        title_present = 1.0 if (card.title and card.title.strip()) else 0.0
        date_present = 1.0 if card.published_at is not None else 0.0
        content_present = 1.0 if (card.cleaned_excerpt and len(card.cleaned_excerpt.strip()) >= 80) else 0.0
        url_present = 1.0 if (card.canonical_url and card.canonical_url.strip()) else 0.0
        metadata_present = 1.0 if (card.entities or card.key_phrases) else 0.0

        return (
            0.30 * title_present
            + 0.30 * date_present
            + 0.30 * content_present
            + 0.05 * url_present
            + 0.05 * metadata_present
        )
