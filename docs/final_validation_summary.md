# Final Validation Summary

Project Atlas reached the current governed warehouse milestone with a successful
full build covering the semantic layer, model-serving marts, and
presentation-basis marts.

## Build Result

| Check | Result |
| --- | --- |
| Full dbt build | PASS |
| Table models | 43 |
| View models | 32 |
| Data tests | 3,044 |
| Total passes | 3,044 |
| Successful models/seeds/snapshots | 76 |
| Warnings | 0 |
| Errors | 0 |
| Skipped | 0 |
| Runtime | 327.24 seconds |
| Artifact generated at | `2026-07-03T23:23:29Z` |

## Completed Scope

- Synthetic raw source system generation.
- DuckDB Bronze warehouse ingestion.
- dbt Silver staging and control layer.
- dbt Gold conformed dimensions, atomic facts, domain marts, and executive marts.
- Final Executive CFO Command Center mart.
- CFO model-serving marts for Excel, React, Power BI, and AI commentary surfaces.
- Presentation-basis marts that separate CFO management views from as-found audit telemetry.

## Recommended Revalidation

For documentation or repository-admin changes:

```bash
git diff
dbt parse --no-partial-parse
```

For full warehouse validation:

```bash
dbt build
```
