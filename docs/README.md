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
| [12_cfo_modelling_layer.md](12_cfo_modelling_layer.md) | CFO model-serving marts for Excel, React, Power BI, and AI commentary. |
| [13_presentation_basis.md](13_presentation_basis.md) | Presented-basis marts: management view over as-found audit telemetry, policy-as-code. |
| [final_validation_summary.md](final_validation_summary.md) | Locked dbt warehouse validation artifact. |

## Current Warehouse Milestone

The governed warehouse, presentation-basis marts, model-serving layer, and live
React dashboard are complete for the current portfolio milestone:

| Metric | Result |
| --- | ---: |
| Table models | 43 |
| View models | 32 |
| Data tests | 3,044 |
| PASS | 3,044 |
| SUCCESS | 76 |
| WARN | 0 |
| ERROR | 0 |
| SKIP | 0 |
| Runtime | 327.24 seconds |

## Completed Phases

| Phase | Status | Summary |
| --- | --- | --- |
| Phase 3 | Complete | Synthetic raw source system generation. |
| Phase 4 | Complete | DuckDB Bronze warehouse ingestion. |
| Phase 5 | Complete | dbt Silver staging and control layer. |
| Phase 6 | Complete | dbt Gold semantic layer. |
| Phase 7 | Complete | Executive CFO Command Center mart. |
| Phase 8 | Live | CFO modelling layer: governed actuals feed, opening balance sheet, readiness controls, and Excel handoff. |
| Phase 9 | Live | Presentation-basis marts and React + DuckDB-WASM CFO intelligence dashboard, deployed to GitHub Pages. |

## Visual Walkthrough

The committed screenshots in [docs/img](img/) mirror the live dashboard route
walkthrough in the root README: Command Center, SaaS Performance, Revenue
Quality, Working Capital, Control Tower, and Forecast & Valuation. Refresh them
from the dashboard workspace with `npm run screenshots` after visible UI
changes.

## Planned Future Work

- Atlas Intelligence Portal (grounded AI commentary over validated mart outputs).

The Power BI CFO pack is superseded by the live React/DuckDB-WASM dashboard; the
[Power BI plan](09_power_bi_reporting_plan.md) is retained as an alternative reference.
