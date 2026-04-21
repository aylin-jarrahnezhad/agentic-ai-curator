import re
from datetime import datetime

from crews.digest_crew import DigestCrew
from models.crew_contracts import DigestSectionResponse
from models.diagnostics import Diagnostics
from models.digest_report import DigestReport
from models.event import Event
from services.digest.summary_utils import summarize_for_digest


class DigestComposer:
    def __init__(self, crew: DigestCrew) -> None:
        self.crew = crew

    def compose(self, events: list[Event], diagnostics: Diagnostics, window: str) -> DigestReport:
        md: DigestSectionResponse = self.crew.compose_digest(
            {
                "events": [e.model_dump(mode="json") for e in events],
                "diagnostics": diagnostics.model_dump(mode="json"),
            }
        )
        return DigestReport(
            title="Weekly AI/Data Digest",
            run_date=datetime.utcnow().strftime("%Y-%m-%d"),
            time_window=window,
            executive_summary=md.executive_summary or "No executive summary generated.",
            top_developments=md.top_developments,
            research_highlights=md.research_highlights,
            company_platform_moves=md.company_platform_moves,
            ecosystem_themes=md.ecosystem_themes,
            methodology_note=md.methodology_note or "Deterministic pipeline + CrewAI reasoning.",
        )

    @staticmethod
    def to_markdown(report: DigestReport, events: list[Event] | None = None, clusters: list[dict] | None = None) -> str:
        if clusters:
            return DigestComposer._cluster_markdown(report, clusters)
        top_text = DigestComposer._clean_section_text(report.top_developments)
        research_text = DigestComposer._clean_section_text(report.research_highlights)
        company_text = DigestComposer._clean_section_text(report.company_platform_moves)
        themes_text = DigestComposer._clean_section_text(report.ecosystem_themes)
        methodology_text = DigestComposer._clean_section_text(report.methodology_note)

        section_links = {"top": "", "research": "", "company": "", "themes": ""}
        if events:
            top_events = DigestComposer._select_related_events(events, top_text)
            research_events = DigestComposer._select_related_events(events, research_text)
            company_events = DigestComposer._select_related_events(events, company_text)
            theme_events = DigestComposer._select_related_events(events, themes_text)
            section_links["top"] = DigestComposer._inline_links(top_events)
            section_links["research"] = DigestComposer._inline_links(research_events)
            section_links["company"] = DigestComposer._inline_links(company_events)
            section_links["themes"] = DigestComposer._inline_links(theme_events)
        return (
            f"# {report.title}\n\nRun date: {report.run_date}  \nTime window: {report.time_window}\n\n"
            f"## Executive Summary\n{report.executive_summary}\n\n## Top Developments\n{top_text}\n{section_links['top']}\n\n"
            f"## Research Highlights\n{research_text}\n{section_links['research']}\n\n"
            f"## Company/Platform Moves\n{company_text}\n{section_links['company']}\n\n"
            f"## Ecosystem Themes\n{themes_text}\n{section_links['themes']}\n\n## Methodology Note\n{methodology_text}\n"
        )

    @staticmethod
    def _inline_links(events: list[Event]) -> str:
        links = [f"[{event.title}]({event.links[0].strip()})" for event in events if event.links]
        if not links:
            return ""
        return "\n### Related Links\n" + "\n".join([f"- {link}" for link in links])

    @staticmethod
    def _clean_section_text(text: str) -> str:
        cleaned = (text or "").strip()
        cleaned = re.sub(r"```[\s\S]*?```", "", cleaned)
        cleaned = cleaned.replace("```", "")
        cleaned = re.sub(r"^##\s+References[\s\S]*$", "", cleaned, flags=re.IGNORECASE | re.MULTILINE)
        return cleaned.strip()

    @staticmethod
    def _select_related_events(events: list[Event], section_text: str, limit: int = 5) -> list[Event]:
        tokens = set(re.findall(r"\b[a-z]{4,}\b", section_text.lower()))
        if not tokens:
            return events[:limit]
        scored: list[tuple[int, Event]] = []
        for event in events:
            hay = f"{event.title} {event.summary} {event.theme_label}".lower()
            overlap = sum(1 for token in tokens if token in hay)
            if overlap > 0:
                scored.append((overlap, event))
        if not scored:
            return events[:limit]
        scored.sort(key=lambda x: x[0], reverse=True)
        seen_ids: set[str] = set()
        selected: list[Event] = []
        for _, event in scored:
            if event.event_id in seen_ids:
                continue
            seen_ids.add(event.event_id)
            selected.append(event)
            if len(selected) >= limit:
                break
        return selected

    @staticmethod
    def _cluster_markdown(report: DigestReport, clusters: list[dict]) -> str:
        lines = [
            f"# {report.title}",
            "",
            f"Run date: {report.run_date}  ",
            f"Time window: {report.time_window}",
            "",
        ]
        for idx, cluster in enumerate(clusters):
            title = (cluster.get("title") or "Untitled").strip()
            summary = summarize_for_digest((cluster.get("summary") or "").strip())
            links = cluster.get("links") or []
            earliest_published_date = cluster.get("earliest_published_date") or cluster.get("earliest_item_date")
            score = cluster.get("score") or {}

            lines.append(f'<div style="font-size: 1.25em;"><strong>{title}</strong></div>')
            if earliest_published_date:
                lines.append(f"Date: {earliest_published_date}")
            if score:
                lines.append(
                    "Scores - "
                    f"relevance: {score.get('mean_relevance', 0)}, "
                    f"importance: {score.get('mean_importance', 0)}, "
                    f"novelty: {score.get('mean_novelty', 0)}, "
                    f"trust: {score.get('mean_trust', 0)}, "
                    f"composed: {score.get('mean_composed', 0)}"
                )
            lines.append("")
            if summary:
                lines.append(summary)
            if links:
                lines.append("")
                lines.append("References:")
                for link in links:
                    lines.append(f"- {link}")
            if idx < len(clusters) - 1:
                lines.append("")
                lines.append('<hr style="border: none; border-top: 1px solid #d3d3d3;" />')
            lines.append("")
        return "\n".join(lines).strip() + "\n"
