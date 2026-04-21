from datetime import UTC, datetime

import requests
from bs4 import BeautifulSoup

from models.raw_item import RawItem
from utils.hashing import sha1_text
from utils.text import canonicalize_url, clean_text, is_informative_paragraph


class SocialFetcher:
    def __init__(self, timeout: int) -> None:
        self.timeout = timeout

    def fetch(self, source: dict, max_items: int) -> list[RawItem]:
        response = requests.get(
            source["api_endpoint"],
            headers={"User-Agent": "weekly-digest-bot/1.0"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        source_id = source["source_id"]
        items: list[RawItem] = []
        if source_id == "github_trending_ai":
            for repo in data.get("items", [])[:max_items]:
                title = clean_text(repo.get("full_name", ""))
                url = canonicalize_url(repo.get("html_url", ""))
                summary = clean_text(repo.get("description") or title)
                items.append(
                    RawItem(
                        id=sha1_text(f"{source_id}|{url}|{title}"),
                        source_id=source_id,
                        connector="social",
                        title=title,
                        summary=summary,
                        links=[url] if url else [],
                        url=url,
                        published_at=repo.get("updated_at"),
                        payload=repo,
                    )
                )
        elif source_id == "hackernews_ai":
            for hit in data.get("hits", [])[:max_items]:
                title = clean_text(hit.get("title") or hit.get("story_title") or "")
                direct_url = hit.get("url") or hit.get("story_url")
                url = canonicalize_url(direct_url or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}")
                summary = clean_text(hit.get("comment_text") or title)
                if len(summary) < 180:
                    fetched_text = self._fetch_article_text(url)
                    if len(fetched_text) > len(summary):
                        summary = fetched_text
                items.append(
                    RawItem(
                        id=sha1_text(f"{source_id}|{url}|{title}"),
                        source_id=source_id,
                        connector="social",
                        title=title,
                        summary=summary,
                        links=[url] if url else [],
                        url=url,
                        published_at=hit.get("created_at"),
                        payload=hit,
                    )
                )
        else:
            for child in data.get("data", {}).get("children", [])[:max_items]:
                post = child.get("data", {})
                title = clean_text(post.get("title", ""))
                candidate_url = post.get("url") or f"https://www.reddit.com{post.get('permalink', '')}"
                url = canonicalize_url(candidate_url)
                summary = clean_text(post.get("selftext", "") or title)
                if len(summary) < 180:
                    fetched_text = self._fetch_article_text(url)
                    if len(fetched_text) > len(summary):
                        summary = fetched_text
                published_at = None
                if post.get("created_utc"):
                    published_at = datetime.fromtimestamp(float(post["created_utc"]), tz=UTC).isoformat()
                items.append(
                    RawItem(
                        id=sha1_text(f"{source_id}|{url}|{title}"),
                        source_id=source_id,
                        connector="social",
                        title=title,
                        summary=summary,
                        links=[url] if url else [],
                        url=url,
                        published_at=published_at,
                        payload=post,
                    )
                )
        return items

    def _fetch_article_text(self, url: str) -> str:
        if not url:
            return ""
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
