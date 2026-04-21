from __future__ import annotations

from crews.digest_crew import DigestCrew


def _test_crew_instance() -> DigestCrew:
    # Build a lightweight instance without running YAML/CrewAI bootstrap.
    crew = DigestCrew.__new__(DigestCrew)
    crew._retry_cooldown_until = 0.0
    return crew


def test_score_evidence_cards_retries_then_succeeds(monkeypatch):
    crew = _test_crew_instance()
    attempts = {"count": 0}

    def fake_json_response(*args, **kwargs):  # noqa: ARG001
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("503 UNAVAILABLE")
        return [
            {
                "id": "card1",
                "semantic_relevance_score": 0.8,
                "semantic_importance_score": 0.7,
                "semantic_novelty_score": 0.6,
                "rationale": "llm ok",
            }
        ]

    monkeypatch.setattr(crew, "_json_response", fake_json_response)
    monkeypatch.setattr("crews.digest_crew.time.sleep", lambda *_: None)

    scored = crew.score_evidence_cards(
        [
            {
                "id": "card1",
                "title": "t",
                "summary": "s",
                "cleaned_excerpt": "e",
                "category": "research",
            }
        ]
    )
    assert attempts["count"] == 3
    assert scored[0].id == "card1"
    assert scored[0].rationale == "llm ok"
    assert scored[0].scoring_source == "llm"


def test_score_evidence_cards_falls_back_after_retries(monkeypatch):
    crew = _test_crew_instance()
    attempts = {"count": 0}

    def always_fail(*args, **kwargs):  # noqa: ARG001
        attempts["count"] += 1
        raise RuntimeError("503 UNAVAILABLE")

    monkeypatch.setattr(crew, "_json_response", always_fail)
    monkeypatch.setattr("crews.digest_crew.time.sleep", lambda *_: None)

    scored = crew.score_evidence_cards(
        [
            {
                "id": "card2",
                "title": "AI update",
                "summary": "benchmark release",
                "cleaned_excerpt": "text",
                "category": "research",
            }
        ]
    )
    assert attempts["count"] == DigestCrew.MAX_LLM_ATTEMPTS
    assert scored[0].id == "card2"
    assert "fallback" in scored[0].rationale.lower()
    assert scored[0].scoring_source == "fallback"


def test_compose_digest_retries_then_parses(monkeypatch):
    crew = _test_crew_instance()
    attempts = {"count": 0}

    def flaky_run(*args, **kwargs):  # noqa: ARG001
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("temporary provider outage")
        return """## Executive Summary
Recovered after retries.

## Top Developments
- Item A
"""

    monkeypatch.setattr(crew, "_run_crewai_task", flaky_run)
    monkeypatch.setattr("crews.digest_crew.time.sleep", lambda *_: None)

    out = crew.compose_digest({"events": [{"title": "x"}], "diagnostics": {}})
    assert attempts["count"] == 3
    assert "Recovered after retries." in out.executive_summary


def test_retry_cooldown_skips_new_llm_attempts(monkeypatch):
    crew = _test_crew_instance()
    crew.RETRY_COOLDOWN_SECONDS = 10
    crew._retry_cooldown_until = 999.0

    # Keep monotonic below cooldown deadline.
    monkeypatch.setattr("crews.digest_crew.time.monotonic", lambda: 100.0)

    attempts = {"count": 0}

    def should_not_run(*args, **kwargs):  # noqa: ARG001
        attempts["count"] += 1
        return []

    monkeypatch.setattr(crew, "_json_response", should_not_run)

    out = crew.score_evidence_cards(
        [
            {
                "id": "cooldown_card",
                "title": "t",
                "summary": "s",
                "cleaned_excerpt": "e",
                "category": "news",
            }
        ]
    )
    assert attempts["count"] == 0
    assert out[0].id == "cooldown_card"
    assert "fallback" in out[0].rationale.lower()
