import json
import re
from urllib.parse import urljoin, urlparse

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

_HTML_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}


class HTMLFetcher:
    def __init__(self, timeout: int) -> None:
        self.timeout = timeout

    @staticmethod
    def _published_from_jsonld(data) -> str | None:
        keys = ("datePublished", "dateModified", "dateCreated", "uploadDate", "publicationDate")
        if isinstance(data, dict):
            for k in keys:
                v = data.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
            graph = data.get("@graph")
            if isinstance(graph, list):
                for node in graph:
                    got = HTMLFetcher._published_from_jsonld(node)
                    if got:
                        return got
            for v in data.values():
                got = HTMLFetcher._published_from_jsonld(v)
                if got:
                    return got
        elif isinstance(data, list):
            for x in data:
                got = HTMLFetcher._published_from_jsonld(x)
                if got:
                    return got
        return None

    @staticmethod
    def _extract_published_from_article_html(soup: BeautifulSoup) -> str | None:
        for prop in (
            "article:published_time",
            "article:modified_time",
            "og:published_time",
            "og:updated_time",
        ):
            tag = soup.find("meta", property=prop)
            if tag and tag.get("content"):
                return tag.get("content", "").strip()
        for name in ("pubdate", "date", "sailthru.date", "article:published_time"):
            tag = soup.find("meta", attrs={"name": name})
            if tag and tag.get("content"):
                return tag.get("content", "").strip()
        for itemprop in ("datePublished", "dateModified", "dateCreated"):
            tag = soup.find(attrs={"itemprop": itemprop})
            if not tag:
                continue
            if tag.get("content"):
                return str(tag.get("content", "")).strip()
            if tag.get("datetime"):
                return str(tag.get("datetime", "")).strip()
            text = tag.get_text(" ", strip=True)
            if text:
                return text
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            raw = script.string or script.get_text() or ""
            if not raw.strip():
                continue
            try:
                data = json.loads(raw)
            except Exception:
                # Some sites inject malformed JSON-LD but still include ISO dates.
                match = re.search(
                    r'"(?:datePublished|dateModified|dateCreated|uploadDate|publicationDate)"\s*:\s*"([^"]+)"',
                    raw,
                )
                if match and match.group(1).strip():
                    return match.group(1).strip()
                continue
            got = HTMLFetcher._published_from_jsonld(data)
            if got:
                return got
        for t in soup.find_all("time"):
            dt = t.get("datetime")
            if dt and str(dt).strip():
                return str(dt).strip()
            text = t.get_text(" ", strip=True)
            if text:
                return text
        return None

    @staticmethod
    def _extract_published_from_text(text: str) -> str | None:
        if not text:
            return None
        match = re.search(
            r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|"
            r"January|February|March|April|June|July|August|September|October|November|December)"
            r"\s+\d{1,2},\s+\d{4}\b",
            text,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        return match.group(0).strip()

    @staticmethod
    def _request_header_profiles() -> list[dict[str, str]]:
        return [
            {"User-Agent": "Mozilla/5.0"},
            {"User-Agent": _HTML_REQUEST_HEADERS["User-Agent"]},
            _HTML_REQUEST_HEADERS,
            {
                "User-Agent": _HTML_REQUEST_HEADERS["User-Agent"],
                "Accept": "text/html,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        ]

    def _request_html(self, url: str) -> str:
        response = None
        for headers in self._request_header_profiles():
            response = requests.get(url, timeout=self.timeout, headers=headers)
            if response.ok:
                return response.text
        if response is not None:
            response.raise_for_status()
        return ""

    def _fetch_listing_html(self, source_url: str) -> str:
        candidate_urls = [source_url, source_url.rstrip("/"), f"{source_url.rstrip('/')}/"]
        seen: set[str] = set()
        last_error: Exception | None = None
        for url in candidate_urls:
            if not url or url in seen:
                continue
            seen.add(url)
            try:
                return self._request_html(url)
            except Exception as exc:
                last_error = exc
                continue
        # Preserve existing behavior: bubble up the latest HTTP error.
        if last_error is not None:
            raise last_error
        return ""

    def fetch(self, source: dict, max_items: int) -> list[RawItem]:
        soup = BeautifulSoup(self._fetch_listing_html(source["url"]), "html.parser")
        base_host = urlparse(source["url"]).netloc.lower()
        path_prefix = (source.get("article_path_prefix") or "").strip().lower()
        sitemap_dates = self._sitemap_lastmod_by_url(source, max_items=max_items)
        items: list[RawItem] = []
        seen_urls: set[str] = set()
        for href in self._candidate_hrefs(soup, source, max_items=max_items):
            parsed = urlparse(href)
            if parsed.scheme not in {"http", "https"}:
                continue
            if base_host and parsed.netloc.lower() != base_host:
                continue
            clean_url = canonicalize_url(href)
            if not clean_url or clean_url in seen_urls:
                continue
            if not is_useful_article_url(clean_url):
                continue
            if path_prefix:
                pth = (urlparse(clean_url).path or "").lower()
                if not pth.startswith(path_prefix) or pth.rstrip("/") == path_prefix.rstrip("/"):
                    continue
            leaf = (urlparse(clean_url).path or "").rstrip("/").split("/")[-1].lower()
            if leaf.endswith((".js", ".css", ".json", ".xml", ".map")):
                continue
            if re.fullmatch(r"page-[0-9a-f]{8,}", leaf):
                continue
            seen_urls.add(clean_url)

            article_title, article_summary, published_at = self._extract_article_fields(clean_url)
            if not published_at:
                published_at = sitemap_dates.get(clean_url)
            if not article_title:
                article_title = clean_text(urlparse(clean_url).path.rsplit("/", 1)[-1].replace("-", " "))
            if not article_title or len(article_title) < 20:
                continue

            item_id = sha1_text(f"{source['source_id']}|{clean_url}|{article_title}")
            items.append(
                RawItem(
                    id=item_id,
                    source_id=source["source_id"],
                    connector="html",
                    title=article_title,
                    summary=article_summary or article_title,
                    links=[clean_url],
                    url=clean_url,
                    published_at=published_at,
                    payload={"page": source["url"]},
                )
            )
            if len(items) >= max_items:
                break
        return items

    def _sitemap_lastmod_by_url(self, source: dict, max_items: int) -> dict[str, str]:
        sitemap_url = (source.get("sitemap_url") or "").strip()
        if not sitemap_url:
            return {}
        try:
            response = requests.get(
                sitemap_url,
                timeout=self.timeout,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            response.raise_for_status()
        except Exception:
            return {}

        xml = response.text or ""
        locs = re.findall(r"<loc>(.*?)</loc>", xml, flags=re.IGNORECASE | re.DOTALL)
        lastmods = re.findall(r"<lastmod>(.*?)</lastmod>", xml, flags=re.IGNORECASE | re.DOTALL)
        pairs: dict[str, str] = {}
        for idx, loc in enumerate(locs[: max_items * 40]):
            clean = canonicalize_url(loc.strip())
            if not clean:
                continue
            if not is_useful_article_url(clean):
                continue
            if idx < len(lastmods):
                lm = (lastmods[idx] or "").strip()
                if lm:
                    pairs[clean] = lm
        return pairs

    @staticmethod
    def _candidate_hrefs(soup: BeautifulSoup, source: dict, max_items: int) -> list[str]:
        # Start with visible anchors.
        hrefs: list[str] = [a.get("href", "") for a in soup.select("a[href]")]
        base_url = source["url"]
        path_prefix = (source.get("article_path_prefix") or "").strip().lower()
        host = urlparse(base_url).netloc.lower()

        # For JS-rendered listing pages, parse embedded scripts for same-host URLs.
        script_text = " ".join((s.string or s.get_text() or "") for s in soup.find_all("script"))
        if script_text:
            blob = script_text.replace("\\/", "/")
            if path_prefix:
                rel_pattern = re.compile(rf"{re.escape(path_prefix)}[A-Za-z0-9/_\-]+")
                for m in rel_pattern.findall(blob):
                    hrefs.append(m if m.startswith("/") else f"/{m}")
            abs_pattern = re.compile(r"https?://[A-Za-z0-9.\-]+/[^\s\"'<>]+")
            for url in abs_pattern.findall(blob):
                if urlparse(url).netloc.lower() == host:
                    hrefs.append(url)

        # Preserve order and avoid unbounded scans.
        out: list[str] = []
        seen: set[str] = set()
        for raw in hrefs:
            full = urljoin(base_url, raw)
            if full in seen:
                continue
            seen.add(full)
            out.append(full)
            if len(out) >= max_items * 20:
                break
        # If listing page is mostly app-shell, or has no links matching the article prefix,
        # use sitemap as candidate source.
        if source.get("sitemap_url"):
            has_prefix_match = False
            if path_prefix:
                for full in out:
                    pth = (urlparse(full).path or "").lower()
                    if not (pth.startswith(path_prefix) and pth.rstrip("/") != path_prefix.rstrip("/")):
                        continue
                    leaf = pth.rstrip("/").split("/")[-1]
                    if leaf.endswith((".js", ".css", ".json", ".xml", ".map")):
                        continue
                    if re.fullmatch(r"page-[0-9a-f]{8,}", leaf):
                        continue
                    has_prefix_match = True
                    break
            if (not out) or (path_prefix and not has_prefix_match):
                sitemap_urls = HTMLFetcher._hrefs_from_sitemap(source, max_items)
                for full in sitemap_urls:
                    if full in seen:
                        continue
                    seen.add(full)
                    out.append(full)
                    if len(out) >= max_items * 20:
                        break
        return out

    @staticmethod
    def _hrefs_from_sitemap(source: dict, max_items: int) -> list[str]:
        sitemap_url = (source.get("sitemap_url") or "").strip()
        if not sitemap_url:
            return []
        try:
            response = requests.get(
                sitemap_url,
                timeout=20,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            response.raise_for_status()
        except Exception:
            return []
        xml = response.text or ""
        urls = [u.strip() for u in re.findall(r"<loc>(.*?)</loc>", xml, flags=re.IGNORECASE | re.DOTALL)]
        path_prefix = (source.get("article_path_prefix") or "").strip().lower()
        filtered: list[str] = []
        for url in urls:
            clean = canonicalize_url(url)
            if not clean:
                continue
            if path_prefix:
                pth = (urlparse(clean).path or "").lower()
                if not pth.startswith(path_prefix) or pth.rstrip("/") == path_prefix.rstrip("/"):
                    continue
            if not is_useful_article_url(clean):
                continue
            filtered.append(clean)
        # Keep freshest-ish items first since sitemaps are usually recent-first.
        return filtered[: max_items * 20]

    def _extract_article_fields(self, url: str) -> tuple[str, str, str | None]:
        try:
            html = self._request_html(url)
        except Exception:
            return "", "", None

        soup = BeautifulSoup(html, "html.parser")
        title = (
            (soup.find("meta", property="og:title") or {}).get("content")
            or (soup.find("meta", attrs={"name": "twitter:title"}) or {}).get("content")
            or (soup.title.string if soup.title and soup.title.string else "")
        )
        title = clean_text(title)

        published = HTMLFetcher._extract_published_from_article_html(soup)
        if not published:
            published = HTMLFetcher._extract_published_from_text(clean_text(soup.get_text(" ", strip=True)))

        summary = self._extract_best_paragraph_text(soup)
        if len(summary) < 180:
            summary = self._extract_text_from_meta_or_jsonld(soup) or summary
        return title, summary, published

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

    def _extract_text_from_meta_or_jsonld(self, soup: BeautifulSoup) -> str:
        meta_candidates = [
            (soup.find("meta", property="og:description") or {}).get("content"),
            (soup.find("meta", attrs={"name": "description"}) or {}).get("content"),
            (soup.find("meta", attrs={"name": "twitter:description"}) or {}).get("content"),
        ]
        for candidate in meta_candidates:
            cleaned = clean_text(candidate or "")
            if len(cleaned) >= 120:
                return cleaned

        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            raw = script.string or script.get_text() or ""
            if not raw.strip():
                continue
            try:
                data = json.loads(raw)
            except Exception:
                continue
            text = self._extract_article_body_from_jsonld(data)
            if len(text) >= 120:
                return text
        return ""

    def _extract_article_body_from_jsonld(self, data) -> str:
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if isinstance(node, dict):
                article_body = node.get("articleBody")
                if isinstance(article_body, str):
                    cleaned = clean_html_text(article_body)
                    if cleaned:
                        return cleaned
                graph = node.get("@graph")
                if isinstance(graph, list):
                    nested = self._extract_article_body_from_jsonld(graph)
                    if nested:
                        return nested
        return ""
