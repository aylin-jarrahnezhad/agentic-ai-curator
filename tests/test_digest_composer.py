from __future__ import annotations

from models.crew_contracts import DigestSectionResponse
from models.diagnostics import Diagnostics
from models.digest_report import DigestReport
from models.event import Event, EventScore
from services.digest.digest_composer import DigestComposer


class _Crew:
    @staticmethod
    def compose_digest(_payload: dict) -> DigestSectionResponse:
        return DigestSectionResponse(
            executive_summary="Executive summary",
            top_developments="Top development text",
            research_highlights="Research highlight text",
            company_platform_moves="Company move text",
            ecosystem_themes="Ecosystem theme text",
            methodology_note="Method note",
        )


def _events() -> list[Event]:
    return [
        Event(
            event_id="e1",
            title="OpenAI model launch",
            summary="A new model release with strong benchmarks.",
            links=["https://example.com/e1"],
            theme_label="models",
            score=EventScore(
                mean_composed=0.9,
                reliability_score=0.9,
                importance_score=0.9,
                novelty_score=0.9,
                combined_score=0.9,
            ),
        ),
        Event(
            event_id="e2",
            title="Research paper",
            summary="A major paper on efficient training and inference.",
            links=["https://example.com/e2"],
            theme_label="research",
            score=EventScore(
                mean_composed=0.8,
                reliability_score=0.8,
                importance_score=0.8,
                novelty_score=0.8,
                combined_score=0.8,
            ),
        ),
    ]


def test_compose_builds_report_sections() -> None:
    composer = DigestComposer(_Crew())
    report = composer.compose(_events(), Diagnostics(), "2026-04-01 to 2026-04-08")

    assert report.title == "Weekly AI/Data Digest"
    assert report.executive_summary == "Executive summary"
    assert report.methodology_note == "Method note"
    assert report.time_window == "2026-04-01 to 2026-04-08"


def test_to_markdown_uses_event_sections_when_no_clusters() -> None:
    report = DigestReport(
        title="Weekly AI/Data Digest",
        run_date="2026-04-21",
        time_window="2026-04-14 to 2026-04-21",
        executive_summary="Executive summary",
        top_developments="Top developments with model launch context",
        research_highlights="Research highlights with training details",
        company_platform_moves="Company platform moves text",
        ecosystem_themes="Ecosystem themes text",
        methodology_note="Methodology note",
    )
    out = DigestComposer.to_markdown(report, events=_events())

    assert "## Top Developments" in out
    assert "### Related Links" in out
    assert "[OpenAI model launch](https://example.com/e1)" in out


def test_to_markdown_uses_cluster_mode_when_clusters_present() -> None:
    report = DigestReport(
        title="Weekly AI/Data Digest",
        run_date="2026-04-21",
        time_window="2026-04-14 to 2026-04-21",
        executive_summary="ignored",
        top_developments="ignored",
        research_highlights="ignored",
        company_platform_moves="ignored",
        ecosystem_themes="ignored",
        methodology_note="ignored",
    )
    clusters = [
        {
            "title": "Cluster A",
            "summary": "Sentence one. Sentence two. Sentence three.",
            "links": ["https://example.com/cluster-a"],
            "earliest_published_date": "2026-04-20",
            "score": {
                "mean_relevance": 0.9,
                "mean_importance": 0.8,
                "mean_novelty": 0.7,
                "mean_trust": 1,
                "mean_composed": 0.85,
            },
        }
    ]
    out = DigestComposer.to_markdown(report, clusters=clusters)

    assert "Cluster A" in out
    assert "References:" in out
    assert "Scores - relevance: 0.9" in out
