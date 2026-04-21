from models.cluster_candidate import ClusterCandidate
from models.event_dossier import EventDossier
from models.evidence_card import EvidenceCard
from utils.text import canonicalize_url, is_useful_article_url


class EventDossierBuilder:
    def build(self, clusters: list[ClusterCandidate], cards_by_id: dict[str, EvidenceCard]) -> list[EventDossier]:
        out: list[EventDossier] = []
        for cluster in clusters:
            cards = [cards_by_id[item_id] for item_id in cluster.item_ids if item_id in cards_by_id]
            if not cards:
                continue
            links = [canonicalize_url(link) for link in cluster.links]
            links = list(dict.fromkeys([link for link in links if link and is_useful_article_url(link)]))
            primary = sorted(set([card.source_id for card in cards if card.source_type == "primary"]))
            secondary = sorted(set([card.source_id for card in cards if card.source_type != "primary"]))
            dates = [card.published_at for card in cards if card.published_at is not None]
            out.append(
                EventDossier(
                    event_id=cluster.cluster_id,
                    title=cluster.title,
                    summary=cluster.summary,
                    links=links,
                    item_ids=cluster.item_ids,
                    primary_source_candidates=primary,
                    secondary_source_candidates=secondary,
                    support_types=sorted(set([card.category for card in cards])),
                    merged_facts=[f"{card.source_id}: {card.title}" for card in cards[:12]],
                    earliest_timestamp=min(dates) if dates else None,
                    latest_timestamp=max(dates) if dates else None,
                    topic_buckets=sorted(set([topic for card in cards for topic in card.likely_topic_buckets])),
                    contradictions=[],
                    source_diversity=len(sorted(set([card.source_id for card in cards]))),
                )
            )
        return out
