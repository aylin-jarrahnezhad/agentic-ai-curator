from __future__ import annotations

import re
from html import unescape


def normalize_summary_text(text: str) -> str:
    normalized = unescape(text)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    normalized = re.sub(r"\s+([,.;:!?])", r"\1", normalized)
    boilerplate_patterns = [
        r"Thank you for visiting nature\.com\..*?without styles and JavaScript\.",
        r"\b[A-Z][a-z]+ [A-Z][a-z]+ is a freelance [^.]+?\.",
        r"Search author on:\s*PubMed Google Scholar",
        r"Credit:\s*[^.]{0,160}\.",
        r"\bAdvertisement\b",
        r"AI-Generated Summary\s*AI-generated content may summarize information incompletely\.\s*Verify important information\.\s*(Learn more)?",
        r"Publish AI,\s*ML\s*&\s*data-science insights to a global community of data professionals\.",
    ]
    for pattern in boilerplate_patterns:
        normalized = re.sub(pattern, " ", normalized, flags=re.IGNORECASE | re.DOTALL)
    normalized = re.sub(r"\b[A-Z][a-z]+ Measuring\b", "Measuring", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def summarize_for_digest(text: str) -> str:
    normalized = normalize_summary_text(text)
    normalized = re.sub(r"The post .*? appeared first on .*?\.", "", normalized, flags=re.IGNORECASE)
    normalized = normalized.replace("[…]", "").replace("…", ".")
    sentences = re.split(r"(?<!\b[A-Z]\.)(?<=[.!?])\s+", normalized)
    sentences = [sentence.strip() for sentence in sentences if sentence.strip()]
    if not sentences:
        return ""
    top = sentences[:6]
    paragraph_one = " ".join(top[:3]).strip()
    paragraph_two = " ".join(top[3:6]).strip()
    if paragraph_two:
        return f"{paragraph_one}\n\n{paragraph_two}"
    return paragraph_one
