import re
from datetime import UTC, datetime

import feedparser
import requests
from bs4 import BeautifulSoup

from models.raw_item import RawItem
from utils.hashing import sha1_text
from utils.text import (
    canonicalize_url,
    clean_html_text,
    clean_text,
    is_informative_paragraph,
    is_useful_article_url,
)

_FEED_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*;q=0.8",
}


class RSSFetcher:
    def __init__(self, timeout: int = 20) -> None:
        self.timeout = timeout

    @staticmethod
    def _entry_published_at(entry) -> str | None:
        for key in ("published", "updated"):
            val = entry.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        for key in ("published_parsed", "updated_parsed"):
            t = entry.get(key)
            if t:
                try:
                    return datetime(
                        t.tm_year,
                        t.tm_mon,
                        t.tm_mday,
                        t.tm_hour,
                        t.tm_min,
                        t.tm_sec,
                        tzinfo=UTC,
                    ).isoformat()
                except Exception:
                    continue
        return None

    def _parse_feed(self, feed_url: str):
        try:
            response = requests.get(
                feed_url,
                timeout=self.timeout,
                headers=_FEED_REQUEST_HEADERS,
            )
            response.raise_for_status()
            return feedparser.parse(response.content)
        except Exception:
            return feedparser.parse(feed_url)

    def fetch(self, source: dict, max_items: int) -> list[RawItem]:
        feed = self._parse_feed(source["feed_url"])
        items: list[RawItem] = []
        for entry in feed.entries[:max_items]:
            url = canonicalize_url(entry.get("link", "") or entry.get("id", ""))
            if not url or not is_useful_article_url(url):
                continue
            summary_text = self._best_available_text(entry)
            fetched_text = self._fetch_article_text(url) if url else ""
            if self._prefer_fetched_text(summary_text, fetched_text):
                summary_text = fetched_text
            title = clean_text(entry.get("title", ""))
            item_id = sha1_text(f"{source['source_id']}|{url}|{title}")
            payload = dict(entry)
            if fetched_text:
                payload["extracted_full_text"] = fetched_text
            items.append(
                RawItem(
                    id=item_id,
                    source_id=source["source_id"],
                    connector="rss",
                    title=title,
                    summary=summary_text or title,
                    links=[url] if url else [],
                    url=url,
                    published_at=self._entry_published_at(entry),
                    payload=payload,
                )
            )
        return items

    @staticmethod
    def _prefer_fetched_text(current_text: str, fetched_text: str) -> bool:
        current = clean_text(current_text)
        fetched = clean_text(fetched_text)
        if not fetched:
            return False
        if not current:
            return True
        teaser_pattern = re.compile(r"\bthe post\b.*\bappeared first on\b", re.IGNORECASE)
        if teaser_pattern.search(current):
            return len(fetched) >= 120
        return len(fetched) > max(300, int(len(current) * 1.2))

    @staticmethod
    def _best_available_text(entry) -> str:
        candidates: list[str] = []
        for content_item in entry.get("content", []) or []:
            if isinstance(content_item, dict):
                candidates.append(clean_html_text(content_item.get("value", "")))
        summary_detail = entry.get("summary_detail", {}) or {}
        if isinstance(summary_detail, dict):
            candidates.append(clean_html_text(summary_detail.get("value", "")))
        candidates.append(clean_html_text(entry.get("summary", "") or entry.get("description", "")))
        candidates = [c for c in candidates if c]
        if not candidates:
            return ""
        # Prefer the richest text source.
        return max(candidates, key=len)

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
        text = self._extract_best_paragraph_text(soup)
        if len(text) >= 180:
            return text
        # Fallback to metadata summaries when pages use scripts for body rendering.
        for tag in (
            soup.find("meta", property="og:description"),
            soup.find("meta", attrs={"name": "description"}),
            soup.find("meta", attrs={"name": "twitter:description"}),
        ):
            if tag and tag.get("content"):
                meta = clean_html_text(tag.get("content", ""))
                if len(meta) >= 120:
                    return meta
        return text

    @staticmethod
    def _extract_best_paragraph_text(soup: BeautifulSoup) -> str:
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
