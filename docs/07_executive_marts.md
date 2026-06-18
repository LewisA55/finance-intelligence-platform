# Executive Marts

The executive mart layer provides CFO-facing reporting surfaces built from governed Gold facts and domain marts.

## Implemented Executive And Domain Marts

| Mart | Primary grain | Purpose |
| --- | --- | --- |
| `mart_financial_performance` | Variance extract line | Actual, budget, forecast, and variance reporting. |
| `mart_o2c_customer_collections` | Customer and invoice month | Billing, collections, open exposure, and allocation quality. |
| `mart_revenue_waterfall` | Customer, reporting month, and currency | Billing-to-recognition waterfall. |
| `mart_deferred_revenue_control` | Period, status, currency, and revenue category | Deferred revenue control and continuity. |
| `mart_ap_working_capital_control` | Vendor and reporting month | AP exposure, payment behaviour, and vendor concentration. |
| `mart_workforce_cost_control` | Department and reporting month | Payroll, headcount, hiring pressure, and workforce controls. |
| `mart_saas_arr_movement` | Month, customer, region, product, and segment | ARR movement waterfall. |
| `mart_saas_retention` | Month, customer, region, and segment | NRR, GRR, logo retention, and SaaS telemetry. |
| `mart_executive_cfo_command_center` | Month and controlled reporting scope | Final CFO command center. |

## CFO Command Center

`mart_executive_cfo_command_center` combines finance, SaaS, O2C, AP, workforce, revenue, and deferred revenue indicators into one executive surface.

It uses controlled reporting scopes:

- Company Total;
- Region Total;
- Business Unit Total.

This is a critical design feature. It prevents incompatible grains from being force-joined and avoids fan-out or double-counting in the reporting layer.

## Scope Rules

| Scope | Intended metrics |
| --- | --- |
| Company Total | Corporate metrics and all rollups that can safely aggregate to company level. |
| Region Total | Customer/region-aligned metrics such as SaaS, revenue waterfall, and O2C. |
| Business Unit Total | Department/business-unit-aligned metrics such as workforce and financial performance. |

Metrics are populated only where the reporting scope is semantically valid.

## BI Consumption

The reporting layer — the live React + DuckDB-WASM dashboard — consumes these marts directly. Core calculations remain in dbt, not in the BI layer.
