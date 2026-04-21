from models.normalized_item import NormalizedItem
from services.preprocess.evidence_builder import EvidenceBuilder


def test_evidence_builder_fields():
    item = NormalizedItem(
        id="1",
        source_id="s",
        source_type="primary",
        category="research",
        trust_tier=5,
        title="OpenAI releases model eval paper",
        summary="Paper introduces new benchmark for model safety.",
        links=["https://example.com/paper"],
        canonical_url="https://example.com/paper",
    )
    card = EvidenceBuilder().build([item])[0]
    assert card.possible_event_type == "research_publication"
    assert card.cleaned_excerpt
