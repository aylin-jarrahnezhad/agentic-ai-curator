from datetime import UTC, datetime

from models.crew_contracts import EvidenceScoreRequest, EvidenceScoreResponse
from models.evidence_card import EvidenceCard
from models.scored_item import ScoreBundle, ScoredItem
from services.scoring.semantic_scoring_service import SemanticScoringService


class PartialCrew:
    def __init__(self) -> None:
        self.calls: list[int] = []

    def score_evidence_cards(self, cards: list[EvidenceScoreRequest]) -> list[EvidenceScoreResponse]:
        self.calls.append(len(cards))
        if len(cards) > 1:
            first = cards[0]
            return [
                EvidenceScoreResponse(
                    id=first.id,
                    semantic_relevance_score=0.9,
                    semantic_importance_score=0.8,
                    semantic_novelty_score=0.7,
                    rationale="batch",
                )
            ]
        only = cards[0]
        return [
            EvidenceScoreResponse(
                id=only.id,
                semantic_relevance_score=0.6,
                semantic_importance_score=0.5,
                semantic_novelty_score=0.4,
                rationale="single",
            )
        ]


def _card(card_id: str) -> EvidenceCard:
    return EvidenceCard(
        id=card_id,
        source_id="source",
        title=f"title {card_id}",
        summary="summary",
        links=["https://example.com"],
        canonical_url=f"https://example.com/{card_id}",
        published_at=datetime(2026, 4, 9, tzinfo=UTC),
        published_date="2026-04-09",
        source_type="primary",
        trust_tier=5,
        category="research",
        cleaned_excerpt="excerpt",
        possible_event_type="release",
    )


def _build_scored_item(card: EvidenceCard, scored_payload: EvidenceScoreResponse | dict | None) -> ScoredItem | None:
    if scored_payload is None:
        return None
    payload = (
        scored_payload
        if isinstance(scored_payload, EvidenceScoreResponse)
        else EvidenceScoreResponse.model_validate(scored_payload)
    )
    composed = round(
        payload.semantic_relevance_score + payload.semantic_importance_score + payload.semantic_novelty_score,
        4,
    )
    return ScoredItem(
        id=card.id,
        title=card.title,
        summary=card.summary,
        links=card.links,
        published_at=card.published_at.isoformat(),
        published_date=card.published_date,
        scores=ScoreBundle(
            relevance=payload.semantic_relevance_score,
            importance=payload.semantic_importance_score,
            novelty=payload.semantic_novelty_score,
            trust=1.0,
            composed=composed,
        ),
        rationale=payload.rationale,
    )


def test_semantic_scoring_service_recovers_missing_cards():
    crew = PartialCrew()
    service = SemanticScoringService(
        crew=crew,
        batch_size=2,
        workers=1,
        build_scored_item=_build_scored_item,
    )

    results = service.score([_card("a"), _card("b")])

    assert len(results) == 2
    assert {item.id for item in results} == {"a", "b"}
    assert crew.calls[0] == 2
    assert any(call == 1 for call in crew.calls[1:])
