# Finance Intelligence Platform

Project Atlas is a portfolio-grade finance analytics engineering project for a fictional multinational SaaS company, Nexus Technologies.

It demonstrates how synthetic enterprise finance data can be generated, loaded into a local DuckDB warehouse, transformed with dbt, validated with automated controls, and shaped into CFO-ready semantic marts.

The project uses synthetic data only. It is designed for portfolio and demonstration purposes, not for production financial reporting.

## Live Dashboard

**https://lewisa55.github.io/finance-intelligence-platform/**

A static, browser-based **CFO intelligence dashboard** built on the governed Gold marts. It
runs entirely client-side — **React + Vite + DuckDB-WASM** query exported Gold Parquet slices
directly in the browser (no backend, no server, self-hosted wasm), enforcing scope-safe
Company-Total reads. Pages:

- **CFO Command Center** — KPI spine, P&L summary, actual vs budget vs forecast, domain health tiles, and a "where to focus next" routing layer.
- **SaaS Performance** — FYTD ARR movement bridge, product-family × segment mix, retention by segment, regional ARR.
- **Financial Performance** — department × account variance vs budget and forecast.
- **Revenue Recognition** — billed vs recognised, deferred-revenue rollforward, and a commercial-ARR-vs-accounting-revenue bridge.
- **Working Capital** — AR collections (by region/segment, top customers) plus AP ageing and vendor exposure.
- **Control Tower** — governed control exceptions by domain and dbt validation evidence.
- **Data & Validation** — loaded tables, row counts, and reporting scopes (auditable provenance).

See [dashboard/README.md](dashboard/README.md) for architecture and how to run it locally.

### Visual Walkthrough

The live dashboard is the canonical interactive walkthrough. Portfolio screenshots will
be added under `docs/img/` as a separate visual-evidence pass.

## Why It Was Built

Nexus Technologies operates across the United Kingdom, United States, Germany, and Singapore. The company has grown rapidly, acquired DataPulse Analytics, and now faces common finance data challenges:

- fragmented source systems;
- inconsistent SaaS KPI definitions;
- multi-currency reporting complexity;
- budget, forecast, and actuals alignment;
- revenue recognition and deferred revenue control;
- executive reporting fan-out risk;
- auditability across finance transformation layers.

Project Atlas solves this by building a governed local finance warehouse with clear Bronze, Silver, and Gold responsibilities.

## Current Status

The dbt warehouse milestone is complete and locked.

| Area | Status |
| --- | --- |
| Synthetic raw source generation | Complete |
| DuckDB Bronze ingestion | Complete |
| dbt Silver staging and controls | Complete |
| dbt Gold semantic layer | Complete |
| Executive CFO Command Center mart | Complete |
| CFO intelligence dashboard (React + DuckDB-WASM) | Live |
| Atlas Intelligence Portal / AI commentary | Planned |

## Final Validation Summary

Latest successful full build:

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

## Tech Stack

| Layer | Technology |
| --- | --- |
| Source generation | Python |
| Local warehouse | DuckDB |
| Transformation | dbt |
| Validation | dbt tests and custom singular tests |
| BI / reporting layer | React + Vite + DuckDB-WASM (in-browser SQL over Parquet) |
| Intelligence layer | Grounded AI commentary, planned |

## Architecture

```text
Synthetic source generation
        |
        v
Raw CSV source files
        |
        v
DuckDB Bronze warehouse
        |
        v
dbt Silver staging and controls
        |
        v
dbt Gold dimensions and facts
        |
        v
Domain marts and executive marts
        |
        v
Executive CFO Command Center
        |
        v
React + DuckDB-WASM CFO dashboard (live) / Atlas Intelligence Portal (planned)
```

## Finance Domains Covered

- General ledger actuals
- Budget and rolling forecast
- Billing, invoicing, payments, and allocations
- Revenue recognition
- Deferred revenue rollforward
- Vendor invoices, payments, and AP ageing
- Workforce compensation, payroll, headcount, and hiring plan
- SaaS subscription events, ARR movement, and retention
- Executive finance performance and CFO command center reporting

ARR in this project represents commercial SaaS run-rate. It is not GAAP revenue. Revenue recognition and deferred revenue are modelled separately as accounting concepts.

## Gold Semantic Layer

Core Gold dimensions:

- `dim_date`
- `dim_gl_account`
- `dim_department`
- `dim_region`
- `dim_customer`
- `dim_vendor`
- `dim_employee`
- `dim_budget_version`
- `dim_forecast_scenario`

Core Gold facts:

- `fct_gl_actuals`
- `fct_budget`
- `fct_forecast`
- `fct_billing_invoices`
- `fct_billing_invoice_lines`
- `fct_billing_payments`
- `fct_billing_payment_allocations`
- `fct_revenue_recognition`
- `fct_deferred_revenue_rollforward`
- `fct_vendor_invoices`
- `fct_vendor_invoice_lines`
- `fct_vendor_payments`
- `fct_ap_ageing_snapshot`
- `fct_employee_compensation`
- `fct_payroll_expense_lines`
- `fct_headcount_snapshot`
- `fct_headcount_plan`
- `fct_subscription_events`
- `fct_subscription_periodic_states`

Gold marts:

- `mart_financial_performance`
- `mart_o2c_customer_collections`
- `mart_revenue_waterfall`
- `mart_deferred_revenue_control`
- `mart_ap_working_capital_control`
- `mart_workforce_cost_control`
- `mart_saas_arr_movement`
- `mart_saas_retention`
- `mart_executive_cfo_command_center`

The Executive CFO Command Center uses controlled reporting scopes to avoid joining incompatible grains:

- Company Total
- Region Total
- Business Unit Total

This prevents fan-out and double-counting when finance, customer, workforce, SaaS, AP, and revenue-control metrics are combined in the dashboard.

## How To Run Locally

Install dependencies:

```bash
pip install -r requirements.txt
```

Generate synthetic source files:

```bash
python scripts/generate_sources.py
```

Run source QA checks:

```bash
python scripts/qa/source_generation_qa.py
python scripts/qa/source_inventory_check.py
```

Load the DuckDB Bronze warehouse:

```bash
python scripts/warehouse/load_raw_to_duckdb.py
```

Validate Bronze:

```bash
python scripts/warehouse/bronze_validation_check.py
```

Run dbt:

```bash
dbt deps
dbt build
```

Generated raw data, warehouse files, dbt targets, and logs are intentionally ignored by Git.

### Run the dashboard

Requires Node.js 22+.

```bash
cd dashboard
npm install
npm run dev      # http://localhost:5173
```

The dashboard reads small committed Parquet slices in `dashboard/public/data/`. After a
new `dbt build` and Parquet export, run `npm run refresh-data` from `dashboard/`. That
single command copies standard exports, rebuilds the curated SaaS/O2C slices, writes a
SHA-256 manifest and validates the complete snapshot.

## Repository Structure

```text
docs/                  Portfolio documentation
dashboard/             React + DuckDB-WASM CFO dashboard (static, deployable to GitHub Pages)
models/                dbt Bronze sources, Silver staging, and Gold semantic models
macros/                dbt helper macros (incl. curated dashboard-slice export macros)
tests/                 dbt singular tests by finance domain
scripts/               Source generation, QA, and warehouse loading scripts
data/                  Local generated raw, processed, and warehouse outputs (ignored)
dbt_project.yml        dbt project configuration
requirements.txt       Python dependencies
```

## Documentation

Start with [docs/README.md](docs/README.md). For the reporting layer, see
[dashboard/README.md](dashboard/README.md) or the
[live dashboard](https://lewisa55.github.io/finance-intelligence-platform/).

## Reporting And Intelligence Layer

The reporting layer is delivered as the **live React + DuckDB-WASM dashboard** above, which
consumes the governed Gold marts and enforces scope-safe Company-Total reads. A Power BI pack
was originally planned ([docs/09_power_bi_reporting_plan.md](docs/09_power_bi_reporting_plan.md));
the React/DuckDB-WASM dashboard **supersedes it** as the realised BI layer, with the Power BI
plan retained as an alternative reference.

The planned Atlas Intelligence Portal / AI commentary layer will summarise validated mart
outputs only — it will not calculate finance metrics independently. The dashboard's narratives
are currently deterministic, generated directly from query results.

## Roadmap

- Wire the dashboard's deterministic narratives to a grounded LLM commentary layer (Atlas Intelligence Portal).
- Add portfolio screenshots from the live dashboard to `docs/img/`.
- Deepen pages as needed (e.g. product-level revenue recognition, true AR ageing slices).
- Continue improving documentation with diagrams and dbt lineage artifacts.

## Author

Lewis Andrews

Finance | Data | Analytics Engineering | Audit Technology
