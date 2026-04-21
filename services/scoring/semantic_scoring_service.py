from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Protocol

from models.crew_contracts import EvidenceScoreRequest, EvidenceScoreResponse
from models.evidence_card import EvidenceCard
from models.scored_item import ScoredItem


class EvidenceScoringCrew(Protocol):
    def score_evidence_cards(
        self,
        cards: list[EvidenceScoreRequest],
    ) -> list[EvidenceScoreResponse]: ...


class SemanticScoringService:
    def __init__(
        self,
        *,
        crew: EvidenceScoringCrew,
        batch_size: int,
        workers: int,
        build_scored_item: Callable[[EvidenceCard, EvidenceScoreResponse | dict | None], ScoredItem | None],
    ) -> None:
        self._crew = crew
        self._batch_size = max(1, int(batch_size))
        self._workers = max(1, int(workers))
        self._build_scored_item = build_scored_item

    def score(self, cards: list[EvidenceCard]) -> list[ScoredItem]:
        out: list[ScoredItem] = []
        batches = [cards[i : i + self._batch_size] for i in range(0, len(cards), self._batch_size)]
        if not batches:
            return out

        with ThreadPoolExecutor(max_workers=self._workers) as executor:
            futures = {
                executor.submit(
                    self._crew.score_evidence_cards,
                    [self._scoring_payload(card) for card in batch],
                ): batch
                for batch in batches
            }
            for future in as_completed(futures):
                batch = futures[future]
                scored = {result.id: result for result in future.result()}
                missing_cards = [card for card in batch if card.id not in scored]
                for _ in range(2):
                    if not missing_cards:
                        break
                    retry_payload = self._crew.score_evidence_cards(
                        [self._scoring_payload(card) for card in missing_cards]
                    )
                    retry_scored = {result.id: result for result in retry_payload}
                    scored.update(retry_scored)
                    missing_cards = [card for card in batch if card.id not in scored]
                if missing_cards:
                    for card in missing_cards:
                        single_payload = self._crew.score_evidence_cards([self._scoring_payload(card)])
                        if isinstance(single_payload, list) and single_payload:
                            scored[card.id] = single_payload[0]
                for card in batch:
                    built = self._build_scored_item(card, scored.get(card.id))
                    if built is not None:
                        out.append(built)
        return sorted(out, key=lambda item: item.scores.composed, reverse=True)

    @staticmethod
    def _scoring_payload(card: EvidenceCard) -> EvidenceScoreRequest:
        return EvidenceScoreRequest(
            id=card.id,
            title=card.title,
            summary=(card.summary or "")[:500],
            cleaned_excerpt=(card.cleaned_excerpt or "")[:900],
            category=card.category,
        )
