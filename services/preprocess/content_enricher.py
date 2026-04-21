import re

from models.normalized_item import NormalizedItem
from utils.text import clean_text, domain_relevance, key_phrases, simple_entities


class ContentEnricher:
    def enrich(self, item: NormalizedItem) -> dict:
        excerpt = clean_text(item.summary)
        text = f"{item.title}. {excerpt}"
        identifiers: dict[str, str] = {}
        doi = re.search(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", text, re.I)
        arxiv = re.search(r"arxiv[:\s]+(\d{4}\.\d{4,5})", text, re.I)
        repo = re.search(r"github\.com/([\w.-]+/[\w.-]+)", " ".join(item.links), re.I)
        if doi:
            identifiers["doi"] = doi.group(0)
        if arxiv:
            identifiers["arxiv_id"] = arxiv.group(1)
        if repo:
            identifiers["repo"] = repo.group(1)
        phrases = key_phrases(text)
        entities = simple_entities(item.title + " " + excerpt)
        buckets = self._topic_buckets(text)
        return {
            "cleaned_excerpt": excerpt,
            "entities": entities,
            "key_phrases": phrases,
            "likely_topic_buckets": buckets,
            "possible_event_type": self._event_type(item.category, buckets),
            "identifiers": identifiers,
            "completeness_flag": bool(item.title and excerpt and item.canonical_url),
            "weak_relevance_score": domain_relevance(text),
        }

    def _topic_buckets(self, text: str) -> list[str]:
        text_lower = text.lower()
        mapping = {
            "llm": ["llm", "gpt", "transformer"],
            "agents": ["agent", "tool use", "autonomous"],
            "mlops": ["deployment", "serving", "inference", "monitoring"],
            "research": ["paper", "benchmark", "evaluation"],
            "data": ["analytics", "warehouse", "data engineering"],
            "code": ["github", "repository", "open source"],
        }
        buckets = [name for name, kws in mapping.items() if any(keyword in text_lower for keyword in kws)]
        return buckets or ["general_ai"]

    def _event_type(self, category: str, buckets: list[str]) -> str:
        if category == "research":
            return "research_publication"
        if "code" in buckets:
            return "code_release"
        if category == "company":
            return "company_announcement"
        if category == "discussion":
            return "community_discussion"
        return "industry_update"
