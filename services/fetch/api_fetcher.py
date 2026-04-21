import feedparser
import requests
from bs4 import BeautifulSoup

from models.raw_item import RawItem
from utils.hashing import sha1_text
from utils.text import canonicalize_url, clean_text, is_informative_paragraph


class APIFetcher:
    def __init__(self, timeout: int) -> None:
        self.timeout = timeout

    def fetch(self, source: dict, max_items: int) -> list[RawItem]:
        sid = source["source_id"]
        if source["connector"] == "arxiv":
            params = {
                "search_query": "all:artificial intelligence",
                "start": 0,
                "max_results": max_items,
            }
            response = requests.get(source["api_endpoint"], params=params, timeout=self.timeout)
            response.raise_for_status()
            parsed = feedparser.parse(response.text)
            result: list[RawItem] = []
            for entry in parsed.entries[:max_items]:
                url = canonicalize_url(entry.get("link", ""))
                title = clean_text(entry.get("title", ""))
                summary = clean_text(entry.get("summary", ""))
                result.append(
                    RawItem(
                        id=sha1_text(f"{sid}|{url}|{title}"),
                        source_id=sid,
                        connector="arxiv",
                        title=title,
                        summary=summary or title,
                        links=[url] if url else [],
                        url=url,
                        published_at=entry.get("published") or entry.get("updated"),
                        payload=dict(entry),
                    )
                )
            return result
        if source["connector"] == "crossref":
            response = requests.get(
                source["api_endpoint"],
                params={"query": "machine learning", "rows": max_items},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            result: list[RawItem] = []
            for item in data.get("message", {}).get("items", [])[:max_items]:
                title = clean_text((item.get("title") or [""])[0])
                doi = item.get("DOI", "")
                url = canonicalize_url(item.get("URL") or (f"https://doi.org/{doi}" if doi else ""))
                abstract = clean_text(item.get("abstract", "") or "")
                date_parts = (
                    (item.get("published-print", {}) or {}).get("date-parts")
                    or (item.get("published-online", {}) or {}).get("date-parts")
                    or (item.get("created", {}) or {}).get("date-parts")
                )
                published = None
                if date_parts and isinstance(date_parts, list) and date_parts[0]:
                    bits = [str(x) for x in date_parts[0][:3]]
                    published = "-".join(bits)
                fetched_text = self._fetch_article_text(url) if url and len(abstract) < 180 else ""
                summary = fetched_text if len(fetched_text) > len(abstract) else abstract
                result.append(
                    RawItem(
                        id=sha1_text(f"{sid}|{doi}|{title}"),
                        source_id=sid,
                        connector="crossref",
                        title=title,
                        summary=summary or title,
                        links=[url] if url else [],
                        url=url,
                        published_at=published,
                        payload=item,
                    )
                )
            return result
        if source["connector"] == "semantic_scholar":
            response = requests.get(
                source["api_endpoint"],
                params={
                    "query": "large language model",
                    "limit": max_items,
                    "fields": "title,abstract,url,year,publicationDate",
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            result: list[RawItem] = []
            for paper in data.get("data", [])[:max_items]:
                title = clean_text(paper.get("title", ""))
                url = canonicalize_url(paper.get("url", ""))
                summary = clean_text(paper.get("abstract", "") or title)
                if url and len(summary) < 180:
                    fetched_text = self._fetch_article_text(url)
                    if len(fetched_text) > len(summary):
                        summary = fetched_text
                published = paper.get("publicationDate") or (str(paper.get("year")) if paper.get("year") else None)
                result.append(
                    RawItem(
                        id=sha1_text(f"{sid}|{url}|{title}"),
                        source_id=sid,
                        connector="semantic_scholar",
                        title=title,
                        summary=summary,
                        links=[url] if url else [],
                        url=url,
                        published_at=published,
                        payload=paper,
                    )
                )
            return result
        return []

    def _fetch_article_text(self, url: str) -> str:
        try:
            response = requests.get(
                url,
                timeout=self.timeout,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0 Safari/537.36"
                    )
                },
            )
            response.raise_for_status()
        except Exception:
            return ""
        soup = BeautifulSoup(response.text, "html.parser")
        candidates = []
        for node in (
            soup.find("article"),
            soup.select_one("main article"),
            soup.select_one("div.prose"),
            soup.select_one("main"),
            soup,
        ):
            if node is None:
                continue
            paragraphs = [p.get_text(" ", strip=True) for p in node.find_all("p")]
            paragraphs = [p for p in paragraphs if is_informative_paragraph(p)]
            text = clean_text(" ".join(paragraphs))
            if text:
                candidates.append(text)
        if not candidates:
            return ""
        return max(candidates, key=len)
