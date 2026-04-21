import collections
import json
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    raw_items = json.loads((root / "outputs" / "intermediate" / "raw_items.json").read_text(encoding="utf-8"))
    fetch_report = json.loads((root / "outputs" / "intermediate" / "fetch_report.json").read_text(encoding="utf-8"))
    failures = {
        row["source_id"]: row["error_message"]
        for row in fetch_report.get("sources", [])
        if row.get("status") == "failed" and row.get("error_message")
    }
    source_registry = json.loads((root / "config" / "source_registry.json").read_text(encoding="utf-8"))["sources"]
    source_ids = [s["source_id"] for s in source_registry]

    by_source: dict[str, list[dict]] = collections.defaultdict(list)
    for item in raw_items:
        by_source[item.get("source_id", "")].append(item)

    print(f"sources_configured={len(source_ids)}")
    print(f"sources_with_items={len(by_source)}")
    print(f"total_items={len(raw_items)}")
    print(f"fetch_failures={fetch_report.get('totals', {}).get('sources_failed', len(failures))}")
    print("\n## Failures")
    for sid in sorted(source_ids):
        if sid in failures:
            print(f"- {sid}: {failures[sid]}")

    print("\n## Coverage by source")
    for sid in sorted(source_ids):
        items = by_source.get(sid, [])
        if not items:
            print(f"- {sid}: n=0, title=0%, body120=0%, date=0%")
            continue
        n = len(items)
        title_ok = sum(1 for i in items if (i.get("title") or "").strip())
        body_ok = sum(1 for i in items if len((i.get("summary") or "").strip()) >= 120)
        date_ok = sum(1 for i in items if i.get("published_at"))
        print(f"- {sid}: n={n}, title={title_ok / n:.0%}, body120={body_ok / n:.0%}, date={date_ok / n:.0%}")


if __name__ == "__main__":
    main()
