# Developer Workflow

## Local Quality Commands

```bash
python -m black . --check
python -m ruff check .
python -m mypy
python -m pytest -q
```

## Test Strategy

- unit tests for stage classes and helpers
- stage flow tests (`run_stage` behavior)
- output store and renderer edge-case tests
- smoke-level pipeline tests with hermetic setup

No external services are required for standard test runs.

## Coverage

- Coverage threshold is enforced in pytest config.
- Coverage data is written to `.pytest_cache/.coverage`.

## CI

GitHub Actions workflow in `.github/workflows/ci.yml` runs format, lint, type check, and tests.
