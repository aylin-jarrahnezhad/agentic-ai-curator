from collections.abc import Mapping
from statistics import mean

from models.crew_contracts import EventSummaryResponse
from models.event import Event, EventScore
from models.event_dossier import EventDossier
from models.scored_item import ScoredItem


class EventScoringService:
    def score_events(
        self,
        dossiers: list[EventDossier],
        item_scores: dict[str, ScoredItem],
        summaries: Mapping[str, EventSummaryResponse | dict[str, object]],
    ) -> list[Event]:
        events: list[Event] = []
        for dossier in dossiers:
            scores = [item_scores[item_id].scores.composed for item_id in dossier.item_ids if item_id in item_scores]
            if not scores:
                continue
            mean_composed = float(mean(scores))
            reliability = min(1.0, 0.2 * len(dossier.primary_source_candidates) + 0.1 * dossier.source_diversity)
            importance = min(1.0, mean_composed + 0.1 * (1 if "company" in dossier.support_types else 0))
            novelty = min(1.0, mean_composed + 0.05 * (1 if "research" in dossier.support_types else 0))
            combined = 0.5 * mean_composed + 0.25 * reliability + 0.15 * importance + 0.10 * novelty
            llm_raw = summaries.get(dossier.event_id)
            llm = (
                llm_raw
                if isinstance(llm_raw, EventSummaryResponse) or llm_raw is None
                else EventSummaryResponse.model_validate(llm_raw)
            )
            events.append(
                Event(
                    event_id=dossier.event_id,
                    title=(llm.title if llm else dossier.title),
                    summary=(llm.summary if llm else dossier.summary),
                    links=dossier.links,
                    earliest_item_date=dossier.earliest_timestamp,
                    item_ids=dossier.item_ids,
                    why_it_matters=(llm.why_it_matters if llm else ""),
                    confidence_note=(llm.confidence_note if llm else ""),
                    theme_label=(llm.theme_label if llm else ""),
                    score=EventScore(
                        mean_composed=round(mean_composed, 4),
                        reliability_score=round(reliability, 4),
                        importance_score=round(importance, 4),
                        novelty_score=round(novelty, 4),
                        combined_score=round(combined, 4),
                    ),
                )
            )
        return sorted(events, key=lambda event: event.score.mean_composed, reverse=True)
