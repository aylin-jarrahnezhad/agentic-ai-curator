"""Run the digest pipeline from the command line."""

from __future__ import annotations

import argparse
from pathlib import Path

from core.pipeline import WeeklyDigestPipeline


def _html_output_name(digest_path: str) -> str:
    return Path(digest_path).with_suffix(".html").name


def main() -> None:
    parser = argparse.ArgumentParser(description="Run weekly digest pipeline by stage.")
    parser.add_argument(
        "--stage",
        choices=["all", "fetch", "score", "cluster", "digest"],
        default="all",
        help="Pipeline stage to run.",
    )
    args = parser.parse_args()

    pipeline = WeeklyDigestPipeline()
    result = pipeline.run() if args.stage == "all" else pipeline.run_stage(args.stage)

    print(f"Weekly digest pipeline stage complete: {args.stage}")
    print(f"- total fetched items: {result.fetched_count}")
    print(f"- total normalized items: {result.normalized_count}")
    print(f"- total evidence cards: {result.evidence_count}")
    print(f"- total refined events: {result.refined_event_count}")
    if result.digest_path:
        html_name = _html_output_name(result.digest_path)
        print(f"- digest output: {result.digest_path}")
        print(f"- digest html object: {html_name}")
        print("- latest html alias: latest.html")
    if result.diagnostics_path:
        print(f"- diagnostics output: {result.diagnostics_path}")


if __name__ == "__main__":
    main()
