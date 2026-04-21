# Outputs and Diagnostics

## Final Outputs (`outputs/`)

- `weekly_digest_YYYY_MM_DD.md`: markdown digest.
- `weekly_digest_YYYY_MM_DD.html`: HTML digest.
- `latest.html`: stable alias to latest digest HTML.
- `weekly_diagnostics_YYYY_MM_DD.md`: compact operational diagnostics.

## Intermediate Outputs (`outputs/intermediate/`)

- `raw_items.json`: fetched raw records.
- `scored_items.json`: semantic scoring output.
- `clustered_items.json`: post-clustering payload.
- `fetch_report.json`: per-source fetch counts, statuses, error details.
- `fetch_report_summary.md`: human-readable fetch summary.

## Diagnostics Structure

The diagnostics markdown emphasizes:

- concise run summary
- fetch health and failures
- scoring quality metrics
- drop counts
- top topic yield
- recommended action items

It also ingests `fetch_report.json` so source-level fetch behavior appears in diagnostics.
