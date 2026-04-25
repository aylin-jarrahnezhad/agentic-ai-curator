from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "export_crispybrain_memories.py"
SPEC = importlib.util.spec_from_file_location("export_crispybrain_memories", SCRIPT_PATH)
assert SPEC is not None
export_crispybrain_memories = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = export_crispybrain_memories
SPEC.loader.exec_module(export_crispybrain_memories)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_export_prefers_clustered_items_and_writes_crispybrain_schema(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "outputs"
    crispybrain_root = tmp_path / "crispybrain"
    write_json(
        outputs_dir / "intermediate" / "clustered_items.json",
        [
            {
                "title": "Aurora Agents Improve Retrieval",
                "summary": "Aurora Agents added a source-grounded retrieval planner for article Q&A.",
                "links": ["https://example.com/aurora-agents"],
                "earliest_published_date": "2026-04-24",
                "item_ids": ["raw-1"],
                "source_ids": ["example_ai_blog"],
                "score": {"mean_composed": 0.91, "mean_relevance": 0.93, "mean_trust": 1.0},
            }
        ],
    )
    write_json(
        outputs_dir / "intermediate" / "scored_items.json",
        [
            {
                "id": "scored-ignored",
                "title": "Scored fallback should not be used",
                "summary": "Clustered output takes precedence.",
                "links": ["https://example.com/scored"],
                "scores": {"composed": 0.99},
            }
        ],
    )

    result = export_crispybrain_memories.export_memories(
        outputs_dir=outputs_dir,
        crispybrain_root=crispybrain_root,
    )

    assert result.source_stage == "clustered"
    project_dir = crispybrain_root / "inbox" / "curated-articles"
    files = list(project_dir.glob("*.txt"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "Project: Curated Articles" in content
    assert "Project slug: curated-articles" in content
    assert "Source/publisher: example_ai_blog" in content
    assert "URL: https://example.com/aurora-agents" in content
    assert "Publish/fetch date: 2026-04-24" in content
    assert "Article summary/body/excerpt:" in content
    assert "source-grounded retrieval planner" in content

    metadata = json.loads((crispybrain_root / "inbox" / ".crispybrain-projects.json").read_text(encoding="utf-8"))
    assert metadata["projects"]["curated-articles"]["display_name"] == "Curated Articles"


def test_export_falls_back_to_scored_items_with_composed_threshold(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "outputs"
    crispybrain_root = tmp_path / "crispybrain"
    write_json(
        outputs_dir / "intermediate" / "scored_items.json",
        [
            {
                "id": "keep",
                "title": "Kept Article",
                "summary": "This article passes the chosen composed-score threshold.",
                "links": ["https://example.com/keep"],
                "published_date": "2026-04-23",
                "source_id": "example_source",
                "scores": {"composed": 0.7, "relevance": 0.75, "importance": 0.8, "novelty": 0.6, "trust": 1.0},
            },
            {
                "id": "drop",
                "title": "Dropped Article",
                "summary": "This article is below threshold.",
                "links": ["https://example.com/drop"],
                "source_id": "example_source",
                "scores": {"composed": 0.69},
            },
        ],
    )

    result = export_crispybrain_memories.export_memories(
        outputs_dir=outputs_dir,
        crispybrain_root=crispybrain_root,
        scored_min_composed=0.7,
    )

    assert result.source_stage == "scored"
    assert result.candidates_exported == 1
    files = list((crispybrain_root / "inbox" / "curated-articles").glob("*.txt"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "Kept Article" in content
    assert "Dropped Article" not in content
    assert "composed: 0.7" in content


def test_export_skips_unchanged_existing_files(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "outputs"
    crispybrain_root = tmp_path / "crispybrain"
    write_json(
        outputs_dir / "intermediate" / "raw_items.json",
        [
            {
                "id": "raw-1",
                "source_id": "raw_source",
                "connector": "rss",
                "title": "Raw Fallback Article",
                "summary": "Raw fallback content is preserved when no richer output exists.",
                "links": ["https://example.com/raw"],
                "published_date": "2026-04-22",
            }
        ],
    )

    first = export_crispybrain_memories.export_memories(
        outputs_dir=outputs_dir,
        crispybrain_root=crispybrain_root,
    )
    second = export_crispybrain_memories.export_memories(
        outputs_dir=outputs_dir,
        crispybrain_root=crispybrain_root,
    )

    assert first.files_written == 1
    assert second.files_written == 0
    assert second.files_skipped == 1
