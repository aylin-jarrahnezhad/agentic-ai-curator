import numpy as np

from models.evidence_card import EvidenceCard
from services.clustering.coarse_clusterer import CoarseClusterer


def test_coarse_clusterer_groups_items():
    cards = [
        EvidenceCard(
            id="1",
            source_id="a",
            title="A",
            summary="A",
            links=["u1"],
            canonical_url="u1",
            source_type="primary",
            trust_tier=5,
            category="company",
            cleaned_excerpt="x",
            possible_event_type="company_announcement",
        ),
        EvidenceCard(
            id="2",
            source_id="b",
            title="B",
            summary="B",
            links=["u2"],
            canonical_url="u2",
            source_type="secondary",
            trust_tier=4,
            category="news",
            cleaned_excerpt="x",
            possible_event_type="industry_update",
        ),
    ]
    clusters = CoarseClusterer().cluster(cards, np.array([[1.0, 0, 0], [0.99, 0.01, 0]]))
    assert len(clusters) >= 1
    assert sum(len(c.item_ids) for c in clusters) == 2
