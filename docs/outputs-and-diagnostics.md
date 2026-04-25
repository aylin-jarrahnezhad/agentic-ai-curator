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

## CrispyBrain Memory Export

Use the export helper after a pipeline run to drop article memories into CrispyBrain:

```bash
python scripts/export_crispybrain_memories.py
```

By default, the helper finds a sibling CrispyBrain repo at `../crispybrain` and writes plain-text inbox files to:

```text
inbox/Curated Articles/
```

The CrispyBrain project key is exactly `Curated Articles`.
The exporter preserves that capitalization and space in the rendered memory content, the direct inbox folder, and the optional CrispyBrain import endpoint payload.

Output selection uses this fallback order:

- `clustered_items.json`
- `scored_items.json`, filtered to `scores.composed >= 0.7`
- `raw_items.json`

All source categories are included.
Each generated memory preserves the title, source/publisher identifier when available, URL, publish/fetch date, summary/body/excerpt text, score metadata, and tags/categories/filter metadata available from the selected curator output.
Existing identical files are skipped so repeated exports do not churn the inbox.

To target a different CrispyBrain checkout or threshold:

```bash
python scripts/export_crispybrain_memories.py \
  --crispybrain-root /path/to/crispybrain \
  --scored-min-composed 0.7
```

When the CrispyBrain local UI is running, prefer the JSON inbox import endpoint:

```bash
python scripts/export_crispybrain_memories.py \
  --crispybrain-import-url http://localhost:8787/api/inbox/import
```

## Diagnostics Structure

The diagnostics markdown emphasizes:

- concise run summary
- fetch health and failures
- scoring quality metrics
- drop counts
- top topic yield
- recommended action items

It also ingests `fetch_report.json` so source-level fetch behavior appears in diagnostics.
