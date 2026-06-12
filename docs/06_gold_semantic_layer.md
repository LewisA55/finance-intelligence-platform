# Gold Semantic Layer

The Gold layer is the conformed semantic layer for Project Atlas.

It transforms source-aligned Silver staging views into finance-ready dimensions, atomic facts, domain marts, and executive marts.

## Gold Principles

- Gold owns enterprise finance definitions.
- Gold models must declare or imply clear business grain.
- BI tools should consume Gold outputs without redefining core business logic.
- Conformed dimensions use deterministic hash keys for cross-source joins.
- Planning models preserve budget versions and forecast scenarios.
- ARR, revenue recognition, deferred revenue, billing, and cash collection remain distinct concepts.

## Core Dimensions

| Dimension | Purpose |
| --- | --- |
| `dim_date` | Shared reporting calendar and date spine. |
| `dim_gl_account` | Conformed chart of accounts. |
| `dim_department` | Department and business unit conformance. |
| `dim_region` | Region and market conformance. |
| `dim_customer` | Customer identity spine. |
| `dim_vendor` | Vendor identity spine. |
| `dim_employee` | Employee identity spine. |
| `dim_budget_version` | Budget version semantics. |
| `dim_forecast_scenario` | Forecast version and scenario semantics. |

## Core Facts

| Fact | Grain summary |
| --- | --- |
| `fct_gl_actuals` | General ledger journal line actuals. |
| `fct_budget` | Budget planning lines by version and planning grain. |
| `fct_forecast` | Forecast lines by version, scenario, and planning grain. |
| `fct_billing_invoices` | Billing invoice headers. |
| `fct_billing_invoice_lines` | Billing invoice lines. |
| `fct_billing_payments` | Billing payments. |
| `fct_billing_payment_allocations` | Payment allocations to invoices. |
| `fct_revenue_recognition` | Revenue recognition schedule rows. |
| `fct_deferred_revenue_rollforward` | Deferred revenue rollforward rows. |
| `fct_vendor_invoices` | Vendor invoice headers. |
| `fct_vendor_invoice_lines` | Vendor invoice lines. |
| `fct_vendor_payments` | Vendor payments. |
| `fct_ap_ageing_snapshot` | AP ageing snapshot rows. |
| `fct_employee_compensation` | Employee compensation rows. |
| `fct_payroll_expense_lines` | Payroll expense lines. |
| `fct_headcount_snapshot` | Monthly headcount snapshots. |
| `fct_headcount_plan` | Planned workforce positions. |
| `fct_subscription_events` | Subscription event ledger. |
| `fct_subscription_periodic_states` | Subscription-month ARR/MRR state fact. |

## Domain And Executive Marts

| Mart | Purpose |
| --- | --- |
| `mart_financial_performance` | Actual, budget, forecast, and variance performance. |
| `mart_o2c_customer_collections` | Customer-month billing and collections exposure. |
| `mart_revenue_waterfall` | Customer-month revenue waterfall and recognition control. |
| `mart_deferred_revenue_control` | Corporate deferred revenue control surface. |
| `mart_ap_working_capital_control` | Vendor-month AP working capital and payment control. |
| `mart_workforce_cost_control` | Department-month workforce cost and headcount control. |
| `mart_saas_arr_movement` | SaaS ARR movement waterfall. |
| `mart_saas_retention` | SaaS retention, NRR, GRR, and logo retention. |
| `mart_executive_cfo_command_center` | Final CFO-level command center. |

## Materialisation

Gold models are materialised as tables to provide stable reporting-ready assets.

## Semantic Guardrails

Gold separates:

- commercial ARR from recognised revenue;
- recognised revenue from deferred revenue;
- invoice billing from cash collection;
- atomic facts from executive marts;
- customer/region grains from department/business-unit grains.

These guardrails make the final reporting layer safer to consume in BI tools.
