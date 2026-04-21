import math
import re
from collections import defaultdict
from urllib.parse import urlparse

from crews.digest_crew import DigestCrew
from models.cluster_candidate import ClusterCandidate
from models.crew_contracts import ClusterRefinementResponse
from utils.logging_utils import get_logger
from utils.text import canonicalize_url, is_useful_article_url

logger = get_logger(__name__)


class ClusterRefinementService:
    # Final safety net against pathological over-merge responses.
    MIN_RETAIN_RATIO = 0.2
    MAX_DOMINANT_CLUSTER_SHARE = 0.45
    _MIN_INPUT_FOR_GLOBAL_GUARDS = 10
    _MIN_TITLE_OVERLAP = 2
    _MIN_TITLE_JACCARD = 0.32
    _STOPWORDS = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "into",
        "about",
        "this",
        "that",
        "these",
        "those",
        "new",
        "update",
        "updates",
        "weekly",
        "report",
        "analysis",
        "announces",
        "launches",
        "launch",
        "introduces",
    }

    def __init__(self, crew: DigestCrew) -> None:
        self.crew = crew

    def refine(self, clusters: list[ClusterCandidate]) -> tuple[list[ClusterCandidate], dict[str, str]]:
        if not clusters:
            return [], {}
        llm: ClusterRefinementResponse = self.crew.refine_clusters([c.model_dump() for c in clusters])
        mapping = self._normalize_mapping(clusters, llm.cluster_mapping)
        labels = llm.labels
        if not mapping:
            return clusters, {c.cluster_id: c.title for c in clusters}
        sanitized_mapping = self._sanitize_mapping(clusters, mapping)
        if sanitized_mapping is None:
            logger.warning(
                "Cluster refinement guardrails rejected LLM mapping; using identity mapping for %s clusters.",
                len(clusters),
            )
            mapping = {cluster.cluster_id: cluster.cluster_id for cluster in clusters}
        else:
            mapping = sanitized_mapping
        merged: dict[str, list[ClusterCandidate]] = defaultdict(list)
        for cluster in clusters:
            merged[mapping.get(cluster.cluster_id, cluster.cluster_id)].append(cluster)
        refined: list[ClusterCandidate] = []
        for cluster_id, group in merged.items():
            links = [canonicalize_url(link) for cluster in group for link in cluster.links]
            links = list(dict.fromkeys([link for link in links if link and is_useful_article_url(link)]))
            refined.append(
                ClusterCandidate(
                    cluster_id=cluster_id,
                    item_ids=[item_id for cluster in group for item_id in cluster.item_ids],
                    title=(labels.get(cluster_id) or self._compose_refined_title(group)),
                    summary=self._merge_cluster_summaries(group),
                    links=links,
                )
            )
        return refined, {cluster.cluster_id: cluster.title for cluster in refined}

    def _normalize_mapping(
        self,
        clusters: list[ClusterCandidate],
        llm_mapping: dict[str, str],
    ) -> dict[str, str]:
        if not llm_mapping:
            return {}
        out: dict[str, str] = {}
        for cluster in clusters:
            target = (llm_mapping.get(cluster.cluster_id) or cluster.cluster_id).strip()
            out[cluster.cluster_id] = target or cluster.cluster_id
        return out

    def _sanitize_mapping(
        self,
        clusters: list[ClusterCandidate],
        mapping: dict[str, str],
    ) -> dict[str, str] | None:
        groups = self._groups_from_mapping(clusters, mapping)
        split_mapping = self._split_unrelated_groups(groups)
        split_groups = self._groups_from_mapping(clusters, split_mapping)
        if self._is_pathological_global_collapse(len(clusters), split_groups):
            return None
        return split_mapping

    def _groups_from_mapping(
        self,
        clusters: list[ClusterCandidate],
        mapping: dict[str, str],
    ) -> dict[str, list[ClusterCandidate]]:
        groups: dict[str, list[ClusterCandidate]] = defaultdict(list)
        for cluster in clusters:
            groups[mapping.get(cluster.cluster_id, cluster.cluster_id)].append(cluster)
        return groups

    def _split_unrelated_groups(self, groups: dict[str, list[ClusterCandidate]]) -> dict[str, str]:
        out: dict[str, str] = {}
        for target_id, group in groups.items():
            if len(group) == 1:
                out[group[0].cluster_id] = target_id
                continue
            components = self._connected_components(group)
            if len(components) == 1:
                for cluster in group:
                    out[cluster.cluster_id] = target_id
                continue
            components = sorted(components, key=lambda comp: (-len(comp), comp[0].cluster_id))
            for idx, comp in enumerate(components):
                comp_target = target_id if idx == 0 else f"{target_id}__split{idx + 1}"
                for cluster in comp:
                    out[cluster.cluster_id] = comp_target
        return out

    def _connected_components(self, group: list[ClusterCandidate]) -> list[list[ClusterCandidate]]:
        by_id = {cluster.cluster_id: cluster for cluster in group}
        adjacency: dict[str, set[str]] = {cluster.cluster_id: set() for cluster in group}
        for i, left in enumerate(group):
            for right in group[i + 1 :]:
                if self._has_strong_merge_evidence(left, right):
                    adjacency[left.cluster_id].add(right.cluster_id)
                    adjacency[right.cluster_id].add(left.cluster_id)
        visited: set[str] = set()
        components: list[list[ClusterCandidate]] = []
        for cluster in group:
            root = cluster.cluster_id
            if root in visited:
                continue
            stack = [root]
            visited.add(root)
            component_ids: list[str] = []
            while stack:
                current = stack.pop()
                component_ids.append(current)
                for nb in adjacency[current]:
                    if nb in visited:
                        continue
                    visited.add(nb)
                    stack.append(nb)
            components.append([by_id[cid] for cid in sorted(component_ids)])
        return components

    def _has_strong_merge_evidence(self, left: ClusterCandidate, right: ClusterCandidate) -> bool:
        if self._shared_canonical_urls(left, right):
            return True
        overlap, jaccard = self._title_overlap(left.title, right.title)
        if overlap < self._MIN_TITLE_OVERLAP or jaccard < self._MIN_TITLE_JACCARD:
            return False
        return self._shares_source_or_entity_cues(left, right)

    def _shared_canonical_urls(self, left: ClusterCandidate, right: ClusterCandidate) -> bool:
        left_urls = {canonicalize_url(link) for link in left.links if link and is_useful_article_url(link)}
        right_urls = {canonicalize_url(link) for link in right.links if link and is_useful_article_url(link)}
        return bool(left_urls.intersection(right_urls))

    def _title_overlap(self, left_title: str, right_title: str) -> tuple[int, float]:
        left_tokens = self._title_tokens(left_title)
        right_tokens = self._title_tokens(right_title)
        if not left_tokens or not right_tokens:
            return 0, 0.0
        overlap = len(left_tokens.intersection(right_tokens))
        union = len(left_tokens.union(right_tokens))
        return overlap, (overlap / float(union) if union else 0.0)

    def _shares_source_or_entity_cues(self, left: ClusterCandidate, right: ClusterCandidate) -> bool:
        left_domains = self._source_domains(left)
        right_domains = self._source_domains(right)
        if left_domains.intersection(right_domains):
            return True
        left_entities = self._entity_cues(left.title)
        right_entities = self._entity_cues(right.title)
        return bool(left_entities.intersection(right_entities))

    def _source_domains(self, cluster: ClusterCandidate) -> set[str]:
        domains: set[str] = set()
        for link in cluster.links:
            if not link:
                continue
            try:
                host = urlparse(canonicalize_url(link)).netloc.lower()
            except Exception:
                host = ""
            if host:
                domains.add(host)
        return domains

    def _title_tokens(self, title: str) -> set[str]:
        return {token for token in re.findall(r"[a-z0-9]{3,}", (title or "").lower()) if token not in self._STOPWORDS}

    def _entity_cues(self, title: str) -> set[str]:
        # Use title entity-like surface forms (acronyms and capitalized terms) as extra merge cues.
        cues = {
            token.lower()
            for token in re.findall(r"\b(?:[A-Z]{2,}|[A-Z][a-z]{2,})\b", title or "")
            if token.lower() not in self._STOPWORDS
        }
        return cues

    def _is_pathological_global_collapse(
        self,
        input_count: int,
        groups: dict[str, list[ClusterCandidate]],
    ) -> bool:
        if input_count < self._MIN_INPUT_FOR_GLOBAL_GUARDS:
            return False
        refined_count = len(groups)
        min_refined = max(2, math.ceil(input_count * self.MIN_RETAIN_RATIO))
        if refined_count < min_refined:
            logger.warning(
                "Cluster mapping collapse guard tripped: input=%s refined=%s min_refined=%s",
                input_count,
                refined_count,
                min_refined,
            )
            return True
        largest_group = max((len(group) for group in groups.values()), default=0)
        if (largest_group / float(input_count)) > self.MAX_DOMINANT_CLUSTER_SHARE:
            logger.warning(
                "Dominant cluster guard tripped: largest_group=%s input=%s share=%.3f",
                largest_group,
                input_count,
                largest_group / float(input_count),
            )
            return True
        return False

    @staticmethod
    def _compose_refined_title(group: list[ClusterCandidate]) -> str:
        unique_titles: list[str] = []
        seen: set[str] = set()
        for cluster in group:
            title = " ".join((cluster.title or "").split()).strip()
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
    def _merge_cluster_summaries(group: list[ClusterCandidate]) -> str:
        snippets: list[str] = []
        seen: set[str] = set()
        for cluster in group:
            text = (cluster.summary or "").strip()
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
