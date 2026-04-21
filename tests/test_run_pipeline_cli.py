from types import SimpleNamespace

import run_pipeline


def test_main_defaults_to_all_stage(monkeypatch, capsys) -> None:
    called = {"run": False, "run_stage": []}

    class DummyPipeline:
        def run(self):
            called["run"] = True
            return SimpleNamespace(
                fetched_count=1,
                normalized_count=1,
                evidence_count=1,
                refined_event_count=1,
                digest_path="",
                diagnostics_path="",
            )

        def run_stage(self, stage: str):
            called["run_stage"].append(stage)
            return SimpleNamespace(
                fetched_count=0,
                normalized_count=0,
                evidence_count=0,
                refined_event_count=0,
                digest_path="",
                diagnostics_path="",
            )

    monkeypatch.setattr(run_pipeline, "WeeklyDigestPipeline", lambda: DummyPipeline())
    monkeypatch.setattr(
        run_pipeline.argparse.ArgumentParser,
        "parse_args",
        lambda _self: SimpleNamespace(stage="all"),
    )

    run_pipeline.main()
    out = capsys.readouterr().out

    assert called["run"] is True
    assert called["run_stage"] == []
    assert "stage complete: all" in out


def test_main_routes_non_all_stage(monkeypatch, capsys) -> None:
    called = {"run": False, "run_stage": []}

    class DummyPipeline:
        def run(self):
            called["run"] = True
            return SimpleNamespace(
                fetched_count=0,
                normalized_count=0,
                evidence_count=0,
                refined_event_count=0,
                digest_path=None,
                diagnostics_path=None,
            )

        def run_stage(self, stage: str):
            called["run_stage"].append(stage)
            return SimpleNamespace(
                fetched_count=1,
                normalized_count=1,
                evidence_count=1,
                refined_event_count=1,
                digest_path="outputs/weekly_digest_2026_04_21.md",
                diagnostics_path="outputs/weekly_diagnostics_2026_04_21.md",
            )

    monkeypatch.setattr(run_pipeline, "WeeklyDigestPipeline", lambda: DummyPipeline())
    monkeypatch.setattr(
        run_pipeline.argparse.ArgumentParser,
        "parse_args",
        lambda _self: SimpleNamespace(stage="score"),
    )

    run_pipeline.main()
    out = capsys.readouterr().out

    assert called["run"] is False
    assert called["run_stage"] == ["score"]
    assert "stage complete: score" in out
    assert "digest html object: weekly_digest_2026_04_21.html" in out
    assert "diagnostics output: outputs/weekly_diagnostics_2026_04_21.md" in out
