# Project Atlas: Gold Semantic Layer Architecture Blueprint

## 1. Purpose

This document defines the architectural requirements for the Project Atlas Gold Semantic Layer.

With the Bronze raw warehouse and Silver staging/control layer now fully locked, the Gold layer becomes the semantic and conformance tier. Its purpose is to transform isolated, source-aligned Silver staging views into a unified, CFO-grade star schema that supports management reporting, financial auditing, Budget vs Actual analysis, forecast variance analysis, control monitoring, and executive commentary.

Gold does not merely make the data easier to query. Gold establishes the single trusted business meaning of Project Atlas finance data.

---

## 2. Architectural Philosophy and Non-Negotiables

The Gold tier is the source of truth for enterprise performance metrics, management reporting, and finance analytics. To prevent metric drift, structural fragmentation, reconciliation failures, or dashboard-specific logic forks, every Gold model must follow the rules below.

### 2.1 Upstream Consumption Invariant

Gold models must consume data exclusively from the Silver staging layer.

Direct consumption of Bronze raw tables, raw CSV files, or external seed files is prohibited unless explicitly approved and documented as a controlled exception.

Allowed:

```text
Silver staging view → Gold dimension / fact / mart
```

Not allowed:

```text
Bronze raw table → Gold model
Raw CSV → Gold model
Power BI transformation → reporting logic
```

### 2.2 Conformed Semantic Spine First

Consumer-facing marts must not be built until the core conformed dimensions are built, tested, and locked.

The following dimensions form the first semantic spine:

```text
dim_date
dim_gl_account
dim_department
dim_region
dim_customer
dim_vendor
dim_employee
dim_budget_version
dim_forecast_scenario
```

### 2.3 Zero BI-Layer Transformation

BI tools must operate as presentation layers only.

Power BI, Tableau, Excel, or HTML dashboards may visualise, filter, and format metrics, but they must not contain core business logic such as:

```text
account classification overrides
department remapping
region remapping
budget/forecast scenario logic
variance favourability logic
ARR / MRR / NRR definitions
control exception logic
```

These definitions belong in Gold SQL.

### 2.4 Absolute Unified Identity

Gold must enforce one shared enterprise definition for:

```text
Department
Region
Account
Customer
Vendor
Employee
Budget Version
Forecast Scenario
```

Application-specific interpretations may exist in Silver, but Gold must resolve them into conformed dimensions.

### 2.5 Explicit Fact Grain Declaration

Every Gold fact model must declare its grain in the model description and in the documentation block.

Example:

```text
fct_budget grain:
one row per budget version, posting period, department, account, currency, and planning driver
```

No fact model should be merged, joined, or consumed downstream unless its grain is explicit.

### 2.6 Explicit Version and Scenario Partitioning

Budget, forecast, and variance models must preserve version and scenario keys.

Gold must not silently collapse:

```text
budget_version_code
forecast_version_code
forecast_scenario
scenario_type
period_status
```

A “latest forecast” view may be created later as a clearly named mart, but core facts must preserve all versions and scenarios.

### 2.7 Traceable Control Marts

Control and exception marts must retain traceability back to Silver and Bronze lineage fields where practical.

At minimum, exception marts should preserve:

```text
source business key
source system
Silver model origin
_atlas_row_hash where available
_atlas_ingested_at where available
_atlas_source_file where available
```

The goal is to allow a finance user or auditor to trace a reported exception back to the originating source extract.

---

## 3. Dimensional Conformance Standards

### 3.1 Deterministic Hash Keys

Gold dimensions should use deterministic hash keys for cross-source joins.

Hash keys should be generated from trimmed, upper-cased natural business keys using a stable hash algorithm.

Example:

```sql
md5(coalesce(trim(upper(account_code)), '')) as gl_account_hk
```

Recommended convention:

```text
<dimension>_hk
```

Examples:

```text
gl_account_hk
department_hk
region_hk
customer_hk
vendor_hk
employee_hk
budget_version_hk
forecast_scenario_hk
```

### 3.2 Natural Keys Must Remain Visible

Hash keys are join keys, not replacements for business keys.

Gold dimensions must preserve natural business keys such as:

```text
account_code
department_id
region_id
customer_id
vendor_id
employee_id
budget_version_code
forecast_version_code
```

This protects interpretability and auditability.

### 3.3 The Unassigned Row Invariant

Every conformed dimension must include a standard fallback row to prevent fact row loss during joins.

Recommended standard:

```text
business key: UNASSIGNED
hash key: md5('UNASSIGNED')
display name: Unassigned
status: System Default
```

Facts with missing, blank, or unmapped natural keys must map to the Unassigned row rather than dropping during joins.

### 3.4 Flattened Hierarchies

Gold dimensions should flatten hierarchies into explicit attributes for reporting performance and semantic clarity.

Examples:

```text
dim_gl_account:
account_code
account_name
account_class
account_type
financial_statement
statement_section
statement_line
normal_balance
is_revenue_account
is_expense_account
is_balance_sheet_account

dim_department:
department_id
department_code
department_name
functional_group
department_group
cost_centre_owner
is_revenue_generating
is_workforce_planning_enabled
```

Nested parent-child structures should not be left for BI tools to resolve.

### 3.5 One Dimension, Multiple Source Inputs

A Gold dimension may combine multiple Silver sources if that is required for conformance.

Example:

```text
dim_department may draw department identifiers from:
- Silver Accounting
- Silver HRIS
- Silver Workforce
- Silver Planning
```

However, the output must be one conformed department dimension.

---

## 4. Gold Model Families

The Gold layer will be organised into four model families.

```text
models/gold/core_dimensions/
models/gold/core_facts/
models/gold/control_marts/
models/gold/executive_marts/
```

### 4.1 Core Dimensions

Core dimensions provide the shared semantic spine.

Initial dimension candidates:

```text
dim_date
dim_gl_account
dim_department
dim_region
dim_customer
dim_vendor
dim_employee
dim_budget_version
dim_forecast_scenario
```

### 4.2 Core Facts

Core facts provide trusted, analysis-ready transaction and planning data.

Initial fact candidates:

```text
fct_gl_actuals
fct_budget
fct_forecast
fct_variance_source
fct_revenue_recognition
fct_deferred_revenue
fct_billing_invoices
fct_cash_collections
fct_ar_ageing
fct_vendor_invoices
fct_vendor_payments
fct_ap_ageing
fct_workforce_actuals
fct_headcount_snapshot
fct_headcount_plan
```

### 4.3 Control Marts

Control marts expose reconciliation, audit, and exception intelligence.

Initial mart candidates:

```text
mart_control_findings
mart_trial_balance_controls
mart_ar_exceptions
mart_ap_exceptions
mart_revenue_recognition_exceptions
mart_workforce_exceptions
mart_planning_exceptions
mart_data_quality_control_tower
```

### 4.4 Executive Marts

Executive marts provide board-pack and CFO-ready outputs.

Initial mart candidates:

```text
mart_pnl_monthly
mart_budget_vs_actual
mart_forecast_vs_budget
mart_variance_analysis
mart_saas_metrics
mart_revenue_waterfall
mart_cash_working_capital
mart_ar_ap_dashboard
mart_workforce_cost_dashboard
mart_cfo_performance_monthly
mart_board_pack_summary
```

---

## 5. Core Blueprint Map

```text
       ┌────────────────────────────────────────────────────────┐
       │                 SILVER STAGING LAYER                   │
       └───────────────────────────┬────────────────────────────┘
                                   │
                                   ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │                      CONFORMED GOLD DIMENSIONS                         │
 ├────────────────────────────────────────────────────────────────────────┤
 │  dim_date               ◄── Temporal spine: fiscal, YTD, rolling views │
 │  dim_gl_account         ◄── Flattened corporate chart of accounts      │
 │  dim_department         ◄── Unified cost centres across finance/HR     │
 │  dim_region             ◄── Standardised geography/entity mappings     │
 │  dim_customer           ◄── Billing and CRM customer identity           │
 │  dim_vendor             ◄── Procurement vendor identity                 │
 │  dim_employee           ◄── HRIS/workforce employee identity            │
 │  dim_budget_version     ◄── Planning version governance                 │
 │  dim_forecast_scenario  ◄── Forecast scenario/version semantics         │
 └─────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │                           GOLD CORE FACTS                              │
 ├────────────────────────────────────────────────────────────────────────┤
 │  fct_gl_actuals              fct_budget              fct_forecast      │
 │  fct_revenue_recognition     fct_ar_ageing           fct_ap_ageing     │
 │  fct_workforce_actuals       fct_headcount_plan      fct_variance      │
 └─────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │                        EXECUTIVE AND CONTROL MARTS                     │
 ├────────────────────────────────────────────────────────────────────────┤
 │  mart_budget_vs_actual       mart_cfo_performance    mart_control_tower│
 │  mart_forecast_vs_budget     mart_workforce_cost     mart_board_pack   │
 └────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Initial Gold Execution Sequence

The Gold layer should be built in controlled phases.

```text
Phase 6A — Gold Semantic Layer Design                 ✅ Design lock
Phase 6B — dim_date                                   Next
Phase 6C — dim_gl_account                             Following
Phase 6D — dim_department / dim_region                Following
Phase 6E — dim_budget_version / dim_forecast_scenario Following
Phase 6F — dim_customer / dim_vendor / dim_employee   Following
Phase 6G — first core finance facts                   Following
Phase 6H — first executive and control marts          Following
```

Recommended first build order:

```text
1. dim_date
2. dim_gl_account
3. dim_department
4. dim_region
5. dim_budget_version
6. dim_forecast_scenario
```

Rationale:

```text
dim_date anchors all period logic.
dim_gl_account anchors finance statement logic.
dim_department and dim_region prevent cross-functional metric drift.
budget and forecast dimensions protect planning version/scenario integrity.
```

---

## 7. First Gold Build Target: dim_date

The first Gold model should be `dim_date`.

`dim_date` should support:

```text
calendar date
calendar year
calendar quarter
calendar month
month start date
month end date
UK fiscal year
UK fiscal quarter
UK fiscal month number
fiscal year label
year-month label
year-month sort
is_month_start
is_month_end
is_quarter_end
is_year_end
```

Project Atlas should use a UK-style fiscal year running April to March unless a later design decision overrides this.

---

## 8. Definition of Done for Gold Models

A Gold model is not locked until it has:

```text
1. Explicit model description.
2. Explicit grain declaration for fact models.
3. Deterministic hash key where appropriate.
4. Natural business key retained.
5. Unassigned row where appropriate for dimensions.
6. Model-level dbt tests.
7. Cross-model control tests where relationships or calculations require them.
8. No direct Bronze dependency.
9. No Power BI-dependent business logic.
10. Clear lineage back to Silver source models.
```

---

## 9. Phase 6A Lock Decision

This document formally establishes the Project Atlas Gold Semantic Layer as the semantic and conformance tier.

With Phase 6A locked, implementation should proceed to:

```text
Phase 6B — Gold dim_date
```
