from models.event_dossier import EventDossier
from models.scored_item import ScoreBundle, ScoredItem
from services.scoring.event_scoring_service import EventScoringService


def test_event_scoring_mean_composed():
    dossier = EventDossier(event_id="e1", title="T", summary="S", links=["u"], item_ids=["i1", "i2"])
    scores = {
        "i1": ScoredItem(
            id="i1",
            title="a",
            summary="s",
            links=["u"],
            scores=ScoreBundle(relevance=1, importance=1, novelty=1, trust=1.0, composed=0.9),
        ),
        "i2": ScoredItem(
            id="i2",
            title="b",
            summary="s",
            links=["u"],
            scores=ScoreBundle(relevance=1, importance=1, novelty=1, trust=1.0, composed=0.7),
        ),
    }
    events = EventScoringService().score_events(
        [dossier], scores, {"e1": {"event_id": "e1", "title": "X", "summary": "Y"}}
    )
    assert events[0].score.mean_composed == 0.8
