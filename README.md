# Finance Intelligence Platform

Project Atlas is a portfolio-grade finance analytics engineering project for a fictional multinational SaaS company, Nexus Technologies.

It demonstrates how synthetic enterprise finance data can be generated, loaded into a local DuckDB warehouse, transformed with dbt, validated with automated controls, and shaped into CFO-ready semantic marts.

The project uses synthetic data only. It is designed for portfolio and demonstration purposes, not for production financial reporting.

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
| Power BI CFO pack | Planned |
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
| BI layer | Power BI, planned |
| Intelligence layer | Streamlit / AI commentary, planned |

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
Power BI CFO pack / Atlas Intelligence Portal (planned)
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

This prevents Power BI fan-out and double-counting when finance, customer, workforce, SaaS, AP, and revenue-control metrics are combined.

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

## Repository Structure

```text
docs/                  Portfolio documentation
models/                dbt Bronze sources, Silver staging, and Gold semantic models
macros/                dbt helper macros
tests/                 dbt singular tests by finance domain
scripts/               Source generation, QA, and warehouse loading scripts
data/                  Local generated raw, processed, and warehouse outputs (ignored)
dbt_project.yml        dbt project configuration
requirements.txt       Python dependencies
```

## Documentation

Start with [docs/README.md](docs/README.md).

## Planned Reporting And Intelligence Layer

Power BI screenshots are not included yet. The planned CFO pack will consume the Gold marts and focus on:

- executive financial performance;
- ARR movement and SaaS retention;
- revenue waterfall and deferred revenue controls;
- O2C collections;
- AP working capital;
- workforce cost controls;
- CFO command center scope views.

The planned Atlas Intelligence Portal / AI commentary layer will summarise validated warehouse outputs only. It will not calculate finance metrics independently.

## Roadmap

- Build Power BI CFO reporting pack.
- Build Atlas Intelligence Portal.
- Add grounded AI commentary from validated mart outputs.
- Add final portfolio screenshots once the reporting layer exists.
- Continue improving documentation with diagrams and dbt lineage artifacts.

## Author

Lewis Andrews

Finance | Data | Analytics Engineering | Audit Technology
