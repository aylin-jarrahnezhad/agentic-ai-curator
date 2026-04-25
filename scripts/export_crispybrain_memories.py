#!/usr/bin/env python3
"""Export curator article outputs into CrispyBrain inbox memory files."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_DISPLAY_NAME = "Curated Articles"
PROJECT_SLUG = "curated-articles"
PROJECT_METADATA_FILE = ".crispybrain-projects.json"
DEFAULT_SCORED_MIN_COMPOSED = 0.7


@dataclass(frozen=True)
class ExportResult:
    source_stage: str
    source_path: Path
    destination_dir: Path
    files_written: int
    files_skipped: int
    candidates_seen: int
    candidates_exported: int


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _nonempty_list(path: Path) -> list[dict[str, Any]] | None:
    if not path.exists():
        return None
    payload = _read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON list at {path}")
    rows = [row for row in payload if isinstance(row, dict)]
    return rows or None


def select_article_rows(outputs_dir: Path, *, scored_min_composed: float) -> tuple[str, Path, list[dict[str, Any]]]:
    """Return rows using fallback order: clustered, then scored, then raw."""
    intermediate_dir = outputs_dir / "intermediate"
    candidates: tuple[tuple[str, Path], ...] = (
        ("clustered", intermediate_dir / "clustered_items.json"),
        ("scored", intermediate_dir / "scored_items.json"),
        ("raw", intermediate_dir / "raw_items.json"),
    )
    for stage, path in candidates:
        rows = _nonempty_list(path)
        if rows is None:
            continue
        if stage == "scored":
            rows = [
                row for row in rows if float((row.get("scores") or {}).get("composed") or 0.0) >= scored_min_composed
            ]
        return stage, path, rows
    raise FileNotFoundError(
        "No non-empty curator article output found. Expected one of "
        "outputs/intermediate/clustered_items.json, scored_items.json, or raw_items.json."
    )


def _slugify(value: str, *, fallback: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value.strip().lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:80].strip("-") or fallback


def _fingerprint(*parts: Any) -> str:
    payload = json.dumps(parts, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _score_lines(score: Any) -> list[str]:
    if not isinstance(score, dict) or not score:
        return []
    lines = ["Scores:"]
    for key in (
        "composed",
        "mean_composed",
        "relevance",
        "mean_relevance",
        "importance",
        "mean_importance",
        "novelty",
        "mean_novelty",
        "trust",
        "mean_trust",
    ):
        if key in score:
            lines.append(f"- {key}: {score[key]}")
    return lines if len(lines) > 1 else []


def _content_or_none(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _source_label(row: dict[str, Any], *, stage: str) -> str:
    if stage == "clustered":
        source_ids = _as_str_list(row.get("source_ids"))
        return ", ".join(source_ids)
    return _content_or_none(row.get("source_id") or row.get("source") or row.get("publisher"))


def _date_label(row: dict[str, Any], *, stage: str) -> str:
    if stage == "clustered":
        return _content_or_none(row.get("earliest_published_date"))
    return _content_or_none(row.get("published_date") or row.get("published_at") or row.get("fetched_at"))


def _tags_for(row: dict[str, Any], *, stage: str) -> list[str]:
    tags = ["agentic-ai-curator", "curated-articles", stage]
    for key in ("category", "source_type", "connector", "scoring_source"):
        value = _content_or_none(row.get(key))
        if value:
            tags.append(value)
    if stage == "clustered":
        tags.extend(_as_str_list(row.get("source_ids")))
    tags.extend(_as_str_list(row.get("tags")))
    return list(dict.fromkeys(tags))


def render_memory(row: dict[str, Any], *, stage: str) -> str:
    title = _content_or_none(row.get("title")) or "Untitled curator article"
    source = _source_label(row, stage=stage)
    date = _date_label(row, stage=stage)
    links = _as_str_list(row.get("links"))
    summary = _content_or_none(row.get("summary") or row.get("cleaned_excerpt") or row.get("excerpt"))
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    if not summary:
        summary = _content_or_none(payload.get("summary") or payload.get("description"))
    tags = _tags_for(row, stage=stage)

    lines = [
        f"# {title}",
        "",
        f"Project: {PROJECT_DISPLAY_NAME}",
        f"Project slug: {PROJECT_SLUG}",
        f"Curator output stage: {stage}",
    ]
    if source:
        lines.append(f"Source/publisher: {source}")
    if links:
        lines.append(f"URL: {links[0]}")
    if date:
        lines.append(f"Publish/fetch date: {date}")
    if tags:
        lines.append(f"Tags/categories/filter metadata: {', '.join(tags)}")

    score = row.get("score") if stage == "clustered" else row.get("scores")
    score_lines = _score_lines(score)
    if score_lines:
        lines.extend(["", *score_lines])

    item_ids = _as_str_list(row.get("item_ids"))
    if item_ids:
        lines.extend(["", f"Curator item ids: {', '.join(item_ids)}"])
    row_id = _content_or_none(row.get("id") or row.get("event_id"))
    if row_id:
        lines.extend(["", f"Curator id: {row_id}"])

    lines.extend(["", "Article summary/body/excerpt:", summary or title])
    if len(links) > 1:
        lines.extend(["", "Additional URLs:", *[f"- {link}" for link in links[1:]]])
    return "\n".join(lines).strip() + "\n"


def memory_filename(row: dict[str, Any], *, stage: str) -> str:
    title = _content_or_none(row.get("title")) or "curated-article"
    stable_id = row.get("event_id") or row.get("id") or row.get("item_ids") or row.get("links") or title
    digest = _fingerprint(stage, stable_id, row.get("links"))
    return f"{_slugify(title, fallback='curated-article')}-{digest}.txt"


def ensure_project_metadata(inbox_dir: Path) -> None:
    metadata_path = inbox_dir / PROJECT_METADATA_FILE
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        metadata = {"projects": {}}
    if not isinstance(metadata, dict):
        metadata = {"projects": {}}
    projects = metadata.setdefault("projects", {})
    if not isinstance(projects, dict):
        metadata["projects"] = projects = {}
    projects[PROJECT_SLUG] = {"display_name": PROJECT_DISPLAY_NAME}
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def export_memories(
    *,
    outputs_dir: Path,
    crispybrain_root: Path,
    scored_min_composed: float = DEFAULT_SCORED_MIN_COMPOSED,
) -> ExportResult:
    stage, source_path, rows = select_article_rows(outputs_dir, scored_min_composed=scored_min_composed)
    inbox_dir = crispybrain_root / "inbox"
    destination_dir = inbox_dir / PROJECT_SLUG
    destination_dir.mkdir(parents=True, exist_ok=True)
    ensure_project_metadata(inbox_dir)

    files_written = 0
    files_skipped = 0
    for row in rows:
        content = render_memory(row, stage=stage)
        destination = destination_dir / memory_filename(row, stage=stage)
        if destination.exists() and destination.read_text(encoding="utf-8") == content:
            files_skipped += 1
            continue
        destination.write_text(content, encoding="utf-8")
        files_written += 1

    return ExportResult(
        source_stage=stage,
        source_path=source_path,
        destination_dir=destination_dir,
        files_written=files_written,
        files_skipped=files_skipped,
        candidates_seen=len(rows),
        candidates_exported=len(rows),
    )


def default_crispybrain_root(curator_root: Path) -> Path:
    sibling = curator_root.parent / "crispybrain"
    if sibling.exists():
        return sibling
    return Path("/Users/elric/repos/crispybrain")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export Agentic AI Curator article outputs as CrispyBrain inbox memory files."
    )
    parser.add_argument(
        "--outputs-dir",
        type=Path,
        default=Path("outputs"),
        help="Curator outputs directory. Defaults to ./outputs.",
    )
    parser.add_argument(
        "--crispybrain-root",
        type=Path,
        default=None,
        help="CrispyBrain repo root. Defaults to sibling ../crispybrain when present.",
    )
    parser.add_argument(
        "--scored-min-composed",
        type=float,
        default=DEFAULT_SCORED_MIN_COMPOSED,
        help="Minimum composed score when falling back to scored_items.json. Defaults to 0.7.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    curator_root = Path(__file__).resolve().parent.parent
    crispybrain_root = args.crispybrain_root or default_crispybrain_root(curator_root)
    result = export_memories(
        outputs_dir=args.outputs_dir,
        crispybrain_root=crispybrain_root,
        scored_min_composed=args.scored_min_composed,
    )
    print(f"CrispyBrain export complete: {result.source_stage} -> {result.destination_dir}")
    print(f"- source: {result.source_path}")
    print(f"- files written: {result.files_written}")
    print(f"- files skipped unchanged: {result.files_skipped}")
    print(f"- project display name: {PROJECT_DISPLAY_NAME}")
    print(f"- project slug: {PROJECT_SLUG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
