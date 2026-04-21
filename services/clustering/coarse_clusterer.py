from collections import defaultdict

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_similarity

from models.cluster_candidate import ClusterCandidate
from models.evidence_card import EvidenceCard
from utils.text import canonicalize_url, is_useful_article_url


class CoarseClusterer:
    # distance = 1 - cosine_similarity on title-only embeddings (see EmbeddingService).
    # Slightly looser than body-rich vectors so paraphrased headlines on the same story can merge.
    DISTANCE_THRESHOLD = 0.40

    def cluster(self, cards: list[EvidenceCard], embeddings: np.ndarray) -> list[ClusterCandidate]:
        if not cards:
            return []
        if len(cards) == 1:
            card = cards[0]
            return [
                ClusterCandidate(
                    cluster_id="cluster_0",
                    item_ids=[card.id],
                    title=card.title,
                    summary=card.summary,
                    links=card.links,
                )
            ]
        sim = cosine_similarity(embeddings)
        dist = 1 - sim
        labels = AgglomerativeClustering(
            metric="precomputed",
            linkage="average",
            distance_threshold=self.DISTANCE_THRESHOLD,
            n_clusters=None,
        ).fit_predict(dist)
        groups: dict[int, list[EvidenceCard]] = defaultdict(list)
        for idx, label in enumerate(labels):
            groups[int(label)].append(cards[idx])
        out: list[ClusterCandidate] = []
        for idx, group in groups.items():
            title = self._compose_cluster_title(group)
            summary = self._compose_cluster_summary(group)
            links = [canonicalize_url(link) for card in group for link in card.links]
            links = list(dict.fromkeys([link for link in links if link and is_useful_article_url(link)]))
            out.append(
                ClusterCandidate(
                    cluster_id=f"cluster_{idx}",
                    item_ids=[card.id for card in group],
                    title=title,
                    summary=summary,
                    links=links,
                )
            )
        return out

    @staticmethod
    def _compose_cluster_title(group: list[EvidenceCard]) -> str:
        if not group:
            return ""
        ranked = sorted(group, key=lambda c: c.source_trust_prior, reverse=True)
        unique_titles: list[str] = []
        seen: set[str] = set()
        for card in ranked:
            title = " ".join((card.title or "").split()).strip()
            if not title:
                continue
            key = title.lower()
            if key in seen:
                continue
            seen.add(key)
            unique_titles.append(title)
        if not unique_titles:
            return ""
        if len(unique_titles) == 1:
            return unique_titles[0]
        lead = " | ".join(unique_titles[:3])
        remaining = len(unique_titles) - 3
        return f"{lead} (+{remaining} more)" if remaining > 0 else lead

    @staticmethod
    def _compose_cluster_summary(group: list[EvidenceCard]) -> str:
        if not group:
            return ""
        ranked = sorted(group, key=lambda c: len((c.cleaned_excerpt or "").strip()), reverse=True)
        snippets: list[str] = []
        seen: set[str] = set()
        for card in ranked:
            text = (card.cleaned_excerpt or card.summary or "").strip()
            if not text:
                continue
            normalized = " ".join(text.split()).lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            snippets.append(" ".join(text.split()))
        if not snippets:
            return ""
        return " ".join(snippets)
