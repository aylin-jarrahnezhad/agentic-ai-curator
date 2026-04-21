import re
import unicodedata
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup

DOMAIN_KEYWORDS = {
    "ai",
    "machine learning",
    "ml",
    "llm",
    "agent",
    "genai",
    "data science",
    "data engineering",
    "analytics",
    "inference",
    "evaluation",
    "benchmark",
    "model",
}
MOJIBAKE_REPLACEMENTS = {
    "â€™": "'",
    "â€˜": "'",
    "â€œ": '"',
    "â€": '"',
    "â€“": "-",
    "â€”": "-",
    "â€¦": "...",
    "Â ": " ",
    "Â": "",
}

BOILERPLATE_PATTERNS = [
    r"Thank you for visiting nature\.com\..*?without styles and JavaScript\.",
    r"You are using a browser version with limited support for CSS\.",
    r"To obtain the best experience, we recommend you use a more up to date browser.*?\.",
    r"Search author on:\s*PubMed Google Scholar",
    r"\bAdvertisement\b",
    r"\b[A-Z][a-z]+ [A-Z][a-z]+ is a freelance [^.]+?\.",
    r"Credit:\s*[^.]{0,160}\.",
    r"AI-Generated Summary\s*AI-generated content may summarize information incompletely\.\s*Verify important information\.\s*(Learn more)?",
    r"Publish AI,\s*ML\s*&\s*data-science insights to a global community of data professionals\.",
    r"\bCookie (policy|preferences|settings)\b",
    r"\bBy using (this|our) (site|website), you (agree|accept)\b.*",
    r"\bSubscribe to (our|the) (newsletter|updates)\b.*",
    r"\bSign in\b|\bLog in\b|\bCreate (an )?account\b",
    r"\bAll rights reserved\b",
    r"\bTerms of (service|use)\b|\bPrivacy policy\b",
    r"\bShare (this|the) article\b",
]

NON_INFORMATIVE_PARAGRAPH_PATTERNS = [
    r"^\s*(advertisement|ad|sponsored)\s*$",
    r"^\s*read (more|next)\s*$",
    r"^\s*(sign in|log in|subscribe)\b.*$",
    r"^\s*(cookie|privacy|terms)\b.*$",
]


def clean_text(text: str) -> str:
    text = text or ""
    text = unicodedata.normalize("NFKC", text)
    for bad, good in MOJIBAKE_REPLACEMENTS.items():
        text = text.replace(bad, good)
    for pattern in BOILERPLATE_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = text.replace("\u00a0", " ").replace("\u200b", "")
    text = re.sub(r"[\u2028\u2029\r\n\t]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_html_text(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "aside"]):
        tag.decompose()
    return clean_text(soup.get_text(" ", strip=True))


def is_informative_paragraph(text: str, min_len: int = 40) -> bool:
    cleaned = clean_text(text)
    if len(cleaned) < min_len:
        return False
    for pattern in NON_INFORMATIVE_PARAGRAPH_PATTERNS:
        if re.search(pattern, cleaned, re.IGNORECASE):
            return False
    return True


def canonicalize_url(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    p = urlparse(url)
    return urlunparse((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), "", "", ""))


# Paths that are usually nav / marketing / legal, not news articles (listing pages may link to these).
GENERIC_PATH_SEGMENTS = {
    "about",
    "about-us",
    "resources",
    "resource",
    "topics",
    "topic",
    "hub",
    "category",
    "categories",
    "tag",
    "tags",
    "latest",
    "careers",
    "jobs",
    "contact",
    "team",
    "leadership",
    "press",
    "privacy",
    "terms",
    "legal",
    "cookies",
    "support",
    "help",
    "login",
    "signin",
    "signup",
    "register",
    "sitemap",
    "search",
}


def is_useful_article_url(url: str) -> bool:
    clean = canonicalize_url(url)
    if not clean:
        return False
    p = urlparse(clean)
    host = p.netloc.lower()
    path = (p.path or "").lower()
    if host.startswith("preview.redd.it"):
        return False
    if re.search(r"\.(png|jpe?g|gif|webp|svg|bmp)$", path):
        return False
    segments = [segment for segment in path.split("/") if segment]
    if not segments:
        return False
    if len(segments) == 1 and segments[0] in GENERIC_PATH_SEGMENTS:
        return False
    if segments[-1] in GENERIC_PATH_SEGMENTS:
        return False
    return True


PROMOTIONAL_PATTERNS = [
    r"\bopen to all\b",
    r"\bstarts tomorrow\b",
    r"\bjoin (our|the) (discord|slack|community)\b",
    r"\bregister now\b",
    r"\bsponsor(?:ed|ing)?\b",
    r"\blivestream(?:ing)?\b",
    r"\bzoom\b",
    r"\bauditing\b",
    r"\bwebinar\b",
    r"\bworkshop\b",
    r"\bseminar\b",
    r"\bcourse\b",
]


def is_digest_worthy_content(title: str, text: str) -> bool:
    haystack = clean_text(f"{title} {text}").lower()
    if not haystack:
        return False
    for pattern in PROMOTIONAL_PATTERNS:
        if re.search(pattern, haystack, re.IGNORECASE):
            return False
    return True


def simple_entities(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\b[A-Z][A-Za-z0-9_-]{2,}\b", text)))[:12]


def key_phrases(text: str, top_n: int = 8) -> list[str]:
    words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
    freq: dict[str, int] = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    return [w for w, _ in sorted(freq.items(), key=lambda x: x[1], reverse=True)[:top_n]]


def domain_relevance(text: str) -> float:
    lower = text.lower()
    hits = sum(1 for kw in DOMAIN_KEYWORDS if kw in lower)
    return min(1.0, hits / 5.0)
