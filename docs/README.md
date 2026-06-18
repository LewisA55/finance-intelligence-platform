# Project Atlas Documentation

This folder contains the portfolio-ready documentation for the Finance Intelligence Platform.

The docs are organised for a hiring manager, finance leader, or data engineer reviewing the project from the outside. They describe what is implemented now, what is planned, and how the warehouse is governed.

The realised reporting layer is the live **React + DuckDB-WASM CFO dashboard** —
[live site](https://lewisa55.github.io/finance-intelligence-platform/) ·
[dashboard/README.md](../dashboard/README.md).

## Recommended Reading Order

| File | Purpose |
| --- | --- |
| [01_project_overview.md](01_project_overview.md) | Business context, scope, completed milestone, and portfolio positioning. |
| [02_architecture.md](02_architecture.md) | Current end-to-end architecture and layer responsibilities. |
| [03_data_generation.md](03_data_generation.md) | Synthetic source generation design, domains, and intentional defects. |
| [04_bronze_layer.md](04_bronze_layer.md) | DuckDB Bronze ingestion contract and validation checkpoint. |
| [05_silver_layer.md](05_silver_layer.md) | dbt Silver staging, source alignment, and control responsibilities. |
| [06_gold_semantic_layer.md](06_gold_semantic_layer.md) | Gold dimensions, facts, marts, grains, and semantic rules. |
| [07_executive_marts.md](07_executive_marts.md) | Domain marts, CFO Command Center, and reporting scope guardrails. |
| [08_testing_and_controls.md](08_testing_and_controls.md) | Final validation summary, test strategy, and finance controls. |
| [09_power_bi_reporting_plan.md](09_power_bi_reporting_plan.md) | Power BI reporting plan (superseded by the live dashboard; kept as reference). |
| [10_ai_commentary_roadmap.md](10_ai_commentary_roadmap.md) | Planned Atlas Intelligence Portal and AI commentary layer. |
| [11_known_limitations.md](11_known_limitations.md) | Accepted caveats, current limitations, and roadmap boundaries. |
| [final_validation_summary.md](final_validation_summary.md) | Locked dbt warehouse validation artifact. |

## Current Warehouse Milestone

The full dbt warehouse milestone is complete and locked:

| Metric | Result |
| --- | ---: |
| Table models | 37 |
| View models | 30 |
| Data tests | 2,946 |
| PASS | 3,013 |
| WARN | 0 |
| ERROR | 0 |
| SKIP | 0 |
| Runtime | 323.70 seconds |

## Completed Phases

| Phase | Status | Summary |
| --- | --- | --- |
| Phase 3 | Complete | Synthetic raw source system generation. |
| Phase 4 | Complete | DuckDB Bronze warehouse ingestion. |
| Phase 5 | Complete | dbt Silver staging and control layer. |
| Phase 6 | Complete | dbt Gold semantic layer. |
| Phase 7 | Complete | Executive CFO Command Center mart. |
| Phase 8 | Live | React + DuckDB-WASM CFO intelligence dashboard (7 pages, deployed to GitHub Pages). |

## Planned Future Work

- Atlas Intelligence Portal (grounded AI commentary over validated mart outputs).
- Portfolio screenshots from the live dashboard.

The Power BI CFO pack is superseded by the live React/DuckDB-WASM dashboard; the
[Power BI plan](09_power_bi_reporting_plan.md) is retained as an alternative reference.
