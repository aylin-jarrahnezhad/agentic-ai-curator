import json
import os
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import yaml

from config.settings import (
    CREW_MAX_LLM_ATTEMPTS,
    CREW_RETRY_BACKOFF_SECONDS,
    CREW_RETRY_COOLDOWN_SECONDS,
    GEMINI_API_KEY,
    GEMINI_MODEL_EASY,
    GEMINI_MODEL_HARD,
)
from models.crew_contracts import (
    ClusterRefinementRequest,
    ClusterRefinementResponse,
    DigestSectionResponse,
    EventSummaryRequest,
    EventSummaryResponse,
    EvidenceScoreRequest,
    EvidenceScoreResponse,
)
from utils.logging_utils import get_logger
from utils.metrics import metrics
from utils.text import domain_relevance

logger = get_logger(__name__)
T = TypeVar("T")


class DigestCrew:
    MAX_LLM_ATTEMPTS = CREW_MAX_LLM_ATTEMPTS
    RETRY_BACKOFF_SECONDS = CREW_RETRY_BACKOFF_SECONDS
    RETRY_COOLDOWN_SECONDS = CREW_RETRY_COOLDOWN_SECONDS

    def __init__(self, agents_path: Path, tasks_path: Path) -> None:
        self.agents_cfg = yaml.safe_load(agents_path.read_text(encoding="utf-8"))
        self.tasks_cfg = yaml.safe_load(tasks_path.read_text(encoding="utf-8"))
        self._crewai_ready = False
        self._retry_cooldown_until: float = 0.0
        self._bootstrap_crewai()

    def _bootstrap_crewai(self) -> None:
        if not GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY is missing; CrewAI tasks cannot run.")
            return
        try:
            from crewai import LLM, Agent, Crew, Process, Task  # type: ignore

            self.Agent = Agent
            self.Crew = Crew
            self.LLM = LLM
            self.Process = Process
            self.Task = Task
            self._crewai_ready = True
        except Exception:
            self._crewai_ready = False

    def _ensure_ready(self) -> None:
        if not self._crewai_ready:
            raise RuntimeError("CrewAI is not ready. Configure GEMINI_API_KEY and provider dependencies.")

    def _resolve_agent_model(self, agent_key: str, harder_task: bool = False) -> str:
        # Priority: explicit env override > agents.yaml llm > global easy/hard default.
        env_key = f"{agent_key.upper()}_LLM"
        env_override = os.getenv(env_key, "").strip()
        if env_override:
            return env_override

        yaml_model = (self.agents_cfg.get(agent_key, {}) or {}).get("llm", "")
        if isinstance(yaml_model, str) and yaml_model.strip():
            return yaml_model.strip()

        return GEMINI_MODEL_HARD if harder_task else GEMINI_MODEL_EASY

    def _run_crewai_task(
        self,
        task_key: str,
        input_payload: list[dict[str, Any]] | dict[str, Any],
        agent_key: str,
        harder_task: bool = False,
    ) -> str | None:
        self._ensure_ready()
        model_name = self._resolve_agent_model(agent_key=agent_key, harder_task=harder_task)
        llm = self.LLM(model=model_name, api_key=GEMINI_API_KEY)
        agent_cfg = self.agents_cfg.get(agent_key, {}) or {}
        task_cfg = self.tasks_cfg.get(task_key, {}) or {}

        agent = self.Agent(
            role=agent_cfg.get("role", agent_key),
            goal=agent_cfg.get("goal", ""),
            backstory=agent_cfg.get("backstory", ""),
            allow_delegation=bool(agent_cfg.get("allow_delegation", False)),
            llm=llm,
        )
        prompt = (
            f"{task_cfg.get('description', '')}\n\n"
            f"Expected Output: {task_cfg.get('expected_output', 'strict JSON')}\n\n"
            "Input JSON:\n"
            f"{json.dumps(input_payload, ensure_ascii=False)[:12000]}\n\n"
            "Return only valid JSON unless markdown is explicitly requested."
        )
        task = self.Task(
            description=prompt,
            expected_output=str(task_cfg.get("expected_output", "strict JSON")),
            agent=agent,
        )
        crew = self.Crew(agents=[agent], tasks=[task], process=self.Process.sequential, verbose=False)
        logger.info("Running CrewAI task=%s with agent=%s model=%s", task_key, agent_key, model_name)
        result = crew.kickoff()
        if hasattr(result, "raw"):
            return result.raw
        return str(result)

    def _json_response(
        self,
        task_key: str,
        input_payload: list[dict[str, Any]] | dict[str, Any],
        agent_key: str,
        harder_task: bool = False,
    ) -> Any:
        self._ensure_ready()
        raw = self._run_crewai_task(
            task_key=task_key,
            input_payload=input_payload,
            agent_key=agent_key,
            harder_task=harder_task,
        )
        if not raw:
            raise RuntimeError(f"CrewAI task={task_key} returned empty output.")
        parsed = self._parse_json_lenient(raw)
        if parsed is None:
            raise ValueError(f"CrewAI task={task_key} did not return parseable JSON.")
        return parsed

    @staticmethod
    def _should_retry_error(exc: Exception) -> bool:
        msg = str(exc).lower()
        # Configuration/setup failures are unlikely to recover with retries.
        if "crewai is not ready" in msg:
            return False
        if "missing" in msg and "api" in msg and "key" in msg:
            return False
        return True

    def _call_with_retries(
        self,
        call: Callable[[], T],
        *,
        task_name: str,
        attempts: int | None = None,
    ) -> T:
        started = time.perf_counter()
        now = time.monotonic()
        if now < self._retry_cooldown_until:
            remaining = self._retry_cooldown_until - now
            metrics.inc("crew.cooldown_skips_total", task=task_name)
            raise RuntimeError(f"{task_name} skipped due to retry cooldown ({remaining:.2f}s remaining).")

        max_attempts = attempts or self.MAX_LLM_ATTEMPTS
        last_exc: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                result = call()
                metrics.inc("crew.llm_calls_success_total", task=task_name)
                metrics.observe("crew.llm_call_seconds", time.perf_counter() - started, task=task_name)
                return result
            except Exception as exc:
                last_exc = exc
                if attempt >= max_attempts or not self._should_retry_error(exc):
                    break
                sleep_s = self.RETRY_BACKOFF_SECONDS * attempt
                metrics.inc("crew.retry_attempts_total", task=task_name)
                logger.warning(
                    "%s attempt %s/%s failed; retrying in %.2fs: %s",
                    task_name,
                    attempt,
                    max_attempts,
                    sleep_s,
                    exc,
                )
                time.sleep(sleep_s)
        if last_exc is not None:
            if self.RETRY_COOLDOWN_SECONDS > 0 and self._should_retry_error(last_exc):
                self._retry_cooldown_until = time.monotonic() + float(self.RETRY_COOLDOWN_SECONDS)
                metrics.inc("crew.cooldown_activations_total", task=task_name)
                metrics.observe("crew.cooldown_seconds", float(self.RETRY_COOLDOWN_SECONDS), task=task_name)
                logger.warning(
                    "%s entering retry cooldown for %ss after repeated failures.",
                    task_name,
                    self.RETRY_COOLDOWN_SECONDS,
                )
            metrics.observe("crew.llm_call_seconds", time.perf_counter() - started, task=task_name)
            raise last_exc
        raise RuntimeError(f"{task_name} failed without a captured exception.")

    def _parse_json_lenient(self, raw: str) -> Any:
        # 1) Direct JSON
        try:
            return json.loads(raw)
        except Exception:
            pass

        # 2) Fenced code block JSON
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw, re.IGNORECASE)
        if fence_match:
            block = fence_match.group(1).strip()
            try:
                return json.loads(block)
            except Exception:
                pass

        # 3) First JSON object or array in text
        object_match = re.search(r"\{[\s\S]*\}", raw)
        if object_match:
            try:
                return json.loads(object_match.group(0))
            except Exception:
                pass
        array_match = re.search(r"\[[\s\S]*\]", raw)
        if array_match:
            try:
                return json.loads(array_match.group(0))
            except Exception:
                pass
        return None

    @staticmethod
    def _fallback_score_card(card: EvidenceScoreRequest) -> EvidenceScoreResponse:
        title = card.title
        summary = card.summary
        excerpt = card.cleaned_excerpt
        category = card.category
        full_text = f"{title} {summary} {excerpt}"
        text = full_text.lower()

        # Relevance-first: DOMAIN_KEYWORDS via domain_relevance(); avoid high scores when text is off-topic.
        dr = domain_relevance(full_text)
        relevance_terms = (
            "machine learning",
            "deep learning",
            "neural",
            "llm",
            "genai",
            "inference",
            "benchmark",
            "transformer",
            "embedding",
        )
        rel_hits = sum(1 for term in relevance_terms if term in text)
        if re.search(r"\bai\b", text):
            rel_hits += 1
        if re.search(r"\bml\b", text):
            rel_hits += 1

        importance_terms = (
            "release",
            "launch",
            "open",
            "acquire",
            "funding",
            "policy",
            "regulation",
            "update",
        )
        novelty_terms = ("new", "first", "novel", "breakthrough", "state-of-the-art", "sota")

        imp_hits = sum(1 for term in importance_terms if term in text)
        nov_hits = sum(1 for term in novelty_terms if term in text)

        text_len_factor = min(len(text), 1200) / 1200.0
        title_len_factor = min(len(title), 120) / 120.0
        category_boost = 0.05 if category.lower() in {"research", "company", "platform"} else 0.0

        relevance = round(
            min(
                1.0,
                0.04 + 0.72 * dr + 0.035 * min(rel_hits, 8) + 0.06 * text_len_factor + category_boost,
            ),
            4,
        )

        imp_raw = min(1.0, 0.10 + 0.10 * imp_hits + 0.14 * title_len_factor + 0.03 * text_len_factor)
        nov_raw = min(1.0, 0.08 + 0.12 * nov_hits + 0.08 * text_len_factor)
        # Tie importance/novelty to relevance so irrelevant articles do not get high composed scores.
        rel_weight = 0.22 + 0.78 * relevance
        importance = round(min(1.0, imp_raw * rel_weight), 4)
        novelty = round(min(1.0, nov_raw * (0.30 + 0.70 * relevance)), 4)

        return EvidenceScoreResponse(
            id=card.id,
            semantic_relevance_score=relevance,
            semantic_importance_score=importance,
            semantic_novelty_score=novelty,
            rationale=("Deterministic fallback (relevance-first heuristic) used because LLM scoring was unavailable."),
            scoring_source="fallback",
        )

    @staticmethod
    def _fallback_cluster_refinement(
        clusters: list[ClusterRefinementRequest],
    ) -> ClusterRefinementResponse:
        mapping = {}
        labels = {}
        for cluster in clusters:
            cluster_id = cluster.cluster_id
            if not cluster_id:
                continue
            mapping[cluster_id] = cluster_id
            labels[cluster_id] = cluster.title.strip() or cluster_id
        return ClusterRefinementResponse(cluster_mapping=mapping, labels=labels)

    @staticmethod
    def _fallback_summaries(dossiers: list[EventSummaryRequest]) -> list[EventSummaryResponse]:
        out: list[EventSummaryResponse] = []
        for dossier in dossiers:
            event_id = dossier.event_id
            title = dossier.title or "Untitled event"
            summary = dossier.summary.strip()
            support_types = dossier.support_types
            topic_buckets = dossier.topic_buckets
            theme_label = str(topic_buckets[0]) if topic_buckets else "general"
            why = (
                f"This event is supported by {len(dossier.item_ids)} items"
                f" across {len(dossier.primary_source_candidates) + len(dossier.secondary_source_candidates)} sources."
            )
            out.append(
                EventSummaryResponse(
                    event_id=event_id,
                    title=title,
                    summary=summary or title,
                    why_it_matters=why,
                    confidence_note=(
                        "Deterministic fallback summary generated due to LLM unavailability. "
                        f"Support types: {', '.join(sorted(set(str(s) for s in support_types))) or 'unknown'}."
                    ),
                    theme_label=theme_label,
                )
            )
        return out

    def score_evidence_cards(self, cards: list[EvidenceScoreRequest | dict[str, Any]]) -> list[EvidenceScoreResponse]:
        if not cards:
            return []
        validated_cards = [EvidenceScoreRequest.model_validate(card) for card in cards]
        payload = [card.model_dump(mode="json") for card in validated_cards]
        try:
            out = self._call_with_retries(
                lambda: self._json_response(
                    task_key="score_evidence_cards",
                    input_payload=payload,
                    agent_key="scoring_agent",
                    harder_task=False,
                ),
                task_name="score_evidence_cards",
            )
            if not isinstance(out, list):
                raise TypeError("score_evidence_cards output must be a JSON list.")
            validated = [EvidenceScoreResponse.model_validate(item) for item in out]
            logger.info(
                "score_evidence_cards: LLM scoring succeeded for %s card(s) (scoring_source=llm).",
                len(validated),
            )
            metrics.inc("crew.scoring_llm_cards_total", len(validated))
            return [r.model_copy(update={"scoring_source": "llm"}) for r in validated]
        except Exception as exc:
            logger.warning("score_evidence_cards fallback activated: %s", exc)
            metrics.inc("crew.fallback_total", task="score_evidence_cards")
            return [self._fallback_score_card(card) for card in validated_cards]

    def refine_clusters(
        self,
        clusters: list[ClusterRefinementRequest | dict[str, Any]],
    ) -> ClusterRefinementResponse:
        if not clusters:
            return ClusterRefinementResponse(cluster_mapping={}, labels={})
        validated_clusters = [ClusterRefinementRequest.model_validate(cluster) for cluster in clusters]
        payload = [cluster.model_dump(mode="json") for cluster in validated_clusters]
        try:
            out = self._call_with_retries(
                lambda: self._json_response(
                    task_key="refine_clusters",
                    input_payload=payload,
                    agent_key="cluster_refinement_agent",
                    harder_task=True,
                ),
                task_name="refine_clusters",
            )
            if not isinstance(out, dict):
                raise TypeError("refine_clusters output must be JSON object with cluster_mapping.")
            return ClusterRefinementResponse.model_validate(out)
        except Exception as exc:
            logger.warning("refine_clusters fallback activated: %s", exc)
            metrics.inc("crew.fallback_total", task="refine_clusters")
            return self._fallback_cluster_refinement(validated_clusters)

    def summarize_event_dossiers(
        self,
        dossiers: list[EventSummaryRequest | dict[str, Any]],
    ) -> list[EventSummaryResponse]:
        if not dossiers:
            return []
        validated_dossiers = [EventSummaryRequest.model_validate(dossier) for dossier in dossiers]
        payload = [dossier.model_dump(mode="json") for dossier in validated_dossiers]
        try:
            out = self._call_with_retries(
                lambda: self._json_response(
                    task_key="summarize_event_dossiers",
                    input_payload=payload,
                    agent_key="event_summary_agent",
                    harder_task=True,
                ),
                task_name="summarize_event_dossiers",
            )
            if not isinstance(out, list):
                raise TypeError("summarize_event_dossiers output must be a JSON list.")
            return [EventSummaryResponse.model_validate(item) for item in out]
        except Exception as exc:
            logger.warning("summarize_event_dossiers fallback activated: %s", exc)
            metrics.inc("crew.fallback_total", task="summarize_event_dossiers")
            return self._fallback_summaries(validated_dossiers)

    def compose_digest(self, payload: dict[str, Any]) -> DigestSectionResponse:
        if not payload.get("events"):
            return DigestSectionResponse(
                executive_summary="No significant events met the weekly criteria.",
                top_developments="- No developments ranked this week.",
                research_highlights="- No research highlights ranked this week.",
                company_platform_moves="- No company/platform moves ranked this week.",
                ecosystem_themes="- Insufficient event density for theme extraction.",
                methodology_note="Built from deterministic evidence processing + CrewAI event reasoning.",
            )
        try:
            raw = self._call_with_retries(
                lambda: self._run_crewai_task(
                    task_key="compose_weekly_digest",
                    input_payload=payload,
                    agent_key="digest_writer_agent",
                    harder_task=True,
                ),
                task_name="compose_weekly_digest",
            )
            if not raw:
                raise RuntimeError("compose_weekly_digest returned empty output.")
            parsed = self._parse_digest_markdown(raw)
            if parsed:
                return DigestSectionResponse.model_validate(parsed)
            logger.warning(
                "compose_weekly_digest returned unparseable markdown; using deterministic fallback digest sections."
            )
        except Exception as exc:
            logger.warning("compose_digest fallback activated: %s", exc)
            metrics.inc("crew.fallback_total", task="compose_weekly_digest")
        return self._fallback_digest_from_events(payload.get("events", []))

    def _parse_digest_markdown(self, raw: str) -> dict[str, str] | None:
        section_map = {
            "executive summary": "executive_summary",
            "top developments": "top_developments",
            "research highlights": "research_highlights",
            "company/platform moves": "company_platform_moves",
            "ecosystem themes": "ecosystem_themes",
            "methodology note": "methodology_note",
        }
        result = {v: "" for v in section_map.values()}
        current_key = None
        for line in raw.splitlines():
            stripped = line.strip()
            header = stripped.lstrip("#").strip().lower()
            if header in section_map:
                current_key = section_map[header]
                continue
            if current_key:
                result[current_key] += line + "\n"
        result = {k: v.strip() for k, v in result.items()}
        if not result["executive_summary"]:
            return None
        return result

    @staticmethod
    def _fallback_digest_from_events(events: list[dict[str, Any]]) -> DigestSectionResponse:
        top = events[:8]
        titles = [e.get("title", "Untitled event") for e in top]
        top_lines = [f"- {title}" for title in titles]
        exec_summary = (
            f"{len(events)} events were ranked this run. " f"Top items include: {', '.join(titles[:3])}."
            if titles
            else "No events were available for digest composition."
        )
        return DigestSectionResponse(
            executive_summary=exec_summary,
            top_developments="\n".join(top_lines[:5]) or "- No developments ranked this week.",
            research_highlights="\n".join(top_lines[1:4]) or "- No research highlights ranked this week.",
            company_platform_moves="\n".join(top_lines[2:5]) or "- No company/platform moves ranked this week.",
            ecosystem_themes="\n".join(top_lines[3:6]) or "- Insufficient event density for theme extraction.",
            methodology_note="Fallback digest sections generated after unparseable LLM markdown response.",
        )
