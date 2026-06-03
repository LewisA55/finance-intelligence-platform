# Finance Intelligence Platform — Data Model Design

## 1. Data Model Objective

Purpose of the model and separation of operational facts from analytical marts.

---

## 2. Business Entities

### Customer

### Product

### Subscription

### Invoice

### Invoice Line

### Opportunity

### Employee

### Department

### GL Account

### Vendor

### Budget

### Forecast

### Exchange Rate

### Region

### Date

For each:

* Description
* Primary Source System

---

## 3. Dimensional Model Overview

### Dimensions

* dim_date
* dim_customer
* dim_product
* dim_department
* dim_region
* dim_account
* dim_vendor
* dim_employee
* dim_scenario

### Operational Facts

* fct_revenue
* fct_expense
* fct_subscriptions
* fct_headcount
* fct_budget
* fct_forecast
* fct_mrr_ledger

### Analytical Marts

* mart_saas_metrics
* mart_finance_kpis
* mart_variance_analysis
* mart_control_tower
* mart_pipeline_to_billing_reconciliation

---

## 4. Dimension Definitions

For every dimension:

### Purpose

### Grain

### Primary Key

### Business Key

### Important Attributes

### Design Notes

Includes:

* dim_date
* dim_customer
* dim_product
* dim_department
* dim_region
* dim_account
* dim_vendor
* dim_employee
* dim_scenario

Important additions:

dim_scenario includes:

* scenario_type
* forecast_version
* currency_treatment
* is_current_forecast

---

## 5. Operational Fact Definitions

### fct_revenue

Grain:

One row per invoice line

Measures:

* gross_amount_local
* discount_amount_local
* net_amount_local
* net_amount_gbp

---

### fct_expense

Grain:

One row per GL posting

Measures:

* expense_amount_local
* expense_amount_gbp

Includes FX account:

7900 - Realised/Unrealised FX Gain/Loss

---

### fct_subscriptions

Grain:

One row per subscription event

Events:

* new
* renewal
* upgrade
* downgrade
* churn
* migration

Additional attribute:

* is_acquired_revenue_event

Purpose:

Separates organic growth from acquisition-driven growth.

---

### fct_mrr_ledger

Grain:

One row per customer-product-subscription-month

Purpose:

Foundation for ARR, MRR, NRR, churn and retention metrics.

---

### fct_headcount

Grain:

One row per employee per month

---

### fct_budget

Grain:

One row per department-account-region-month-scenario

---

### fct_forecast

Grain:

One row per department-account-region-month-forecast-version

---

## 6. Design Principle: Operational Facts vs Analytical Marts

Operational Facts answer:

"What happened?"

Analytical Marts answer:

"What does it mean?"

Benefits:

* Stable transaction layer
* Flexible KPI definitions
* Easier governance
* Easier Power BI development

---

## 7. Analytical Mart Definitions

### mart_saas_metrics

Purpose:

Executive SaaS reporting.

Grain:

One row per reporting month.

Outputs:

* ARR
* MRR
* NRR
* GRR
* Expansion ARR
* Contraction ARR
* Churn

Inputs:

* fct_subscriptions
* fct_mrr_ledger

---

### mart_finance_kpis

Purpose:

Executive finance reporting.

Grain:

One row per reporting month.

Outputs:

* Revenue
* Gross Profit
* EBITDA
* EBITDA Margin
* Revenue Per Employee
* Cost Per Employee
* Rule Of 40

Inputs:

* fct_revenue
* fct_expense
* fct_headcount
* mart_saas_metrics

Design Note:
Rule of 40 is calculated by combining revenue growth from mart_saas_metrics with EBITDA margin from mart_finance_kpis.
---

### mart_variance_analysis

Purpose:

Budget and forecast comparison.

Grain:

One row per metric-month-scenario.

Outputs:

* Actual
* Budget
* Forecast
* Variance
* Variance %

Inputs:

* fct_budget
* fct_forecast
* mart_finance_kpis

---

### mart_pipeline_to_billing_reconciliation

Purpose:

Reconcile CRM opportunities against billing subscriptions.

Grain:

One row per CRM opportunity.

Inputs:

* crm_opportunities
* fct_subscriptions

Outputs:

* Missing Subscription
* Delayed Provisioning
* Start Date Mismatch
* Contract Value Mismatch

Design Note:

Acts as the bridge between Sales Operations and Finance Operations.

---

### mart_control_tower

Purpose:

Provide trust and governance reporting.

Grain:

One row per control execution.

Outputs:

* Failed Controls
* Severity
* Impacted Records
* Owner
* Status

---

## 8. Key Modelling Decisions

### DataPulse Acquisition

Challenges:

* Different customer IDs
* Different product catalogue
* Employee migration

Solutions:

* global_customer_id
* customer_identity_map
* PulseEngine product mapping
* acquisition revenue flags

---

### Multi-Currency Reporting

Source currencies:

* GBP
* USD
* EUR
* SGD

Group currency:

* GBP

Required fields:

* local_amount
* currency_code
* fx_rate_to_gbp
* amount_gbp

Supports:

* Reported Growth
* Constant Currency Growth
* FX Impact

---

### Date Spine

Coverage:

2022-01-01 to 2026-12-31

Purpose:

* Time intelligence
* Subscription expansion
* Budget alignment
* Forecast alignment

---

## 9. Data Quality & Control Requirements

Required control categories:

### Data Quality

* Null keys
* Duplicate records
* Invalid values

### Finance Controls

* Revenue reconciliation
* Expense reconciliation
* Budget completeness
* Forecast completeness

### Revenue Operations Controls

* CRM vs Billing reconciliation
* Missing subscriptions
* Delayed provisioning

### FX Controls

* Missing FX rates
* Invalid currencies
* FX conversion validation

These controls feed mart_control_tower.

---

## 10. Phase 2 Completion Criteria

The data model is complete when:

* Business entities are defined
* Dimensions are defined
* Fact grains are defined
* Analytical marts are defined
* Acquisition modelling is defined
* FX modelling is defined
* Date spine design is defined
* Control requirements are defined

## 11. Model Relationship Overview

The Finance Intelligence Platform follows a layered dimensional architecture.

Business entities are represented through dimensions and operational facts.

Operational facts are then transformed into analytical marts, which provide executive-ready metrics for Power BI and AI-assisted reporting.

### SaaS Revenue Flow

```text
dim_customer
        │
        │
dim_product
        │
        │
        ▼
fct_subscriptions
        │
        │
        ▼
fct_mrr_ledger
        │
        │
        ▼
mart_saas_metrics
        │
        │
        ▼
Power BI
```

Purpose:

```text
Customer lifecycle tracking
ARR
MRR
NRR
GRR
Expansion ARR
Contraction ARR
Churn analysis
Revenue growth input for Rule of 40
```

---

### Billing Revenue Flow

```text
dim_customer
        │
dim_product
        │
dim_region
        │
        ▼
fct_revenue
        │
        ▼
mart_finance_kpis
        │
        ▼
Power BI
```

Purpose:

```text
Revenue reporting
Regional analysis
Product analysis
Customer analysis
Executive KPI reporting
```

---

### Expense & Profitability Flow

```text
dim_department
        │
dim_account
        │
dim_vendor
        │
dim_region
        │
        ▼
fct_expense
        │
        ▼
mart_finance_kpis
        │
        ▼
Power BI
```

Purpose:

```text
Operating expense reporting
Department analysis
EBITDA reporting
Margin analysis
Budget variance analysis
```

---

### Headcount Flow

```text
dim_employee
        │
dim_department
        │
dim_region
        │
        ▼
fct_headcount
        │
        ▼
mart_finance_kpis
        │
        ▼
Power BI
```

Purpose:

```text
Headcount trends
Revenue per employee
Cost per employee
Workforce analysis
```

---

### Budget & Forecast Flow

```text
dim_department
        │
dim_account
        │
dim_region
        │
dim_scenario
        │
        ├──────────────┐
        │              │
        ▼              ▼
fct_budget    fct_forecast
        │              │
        └──────┬───────┘
               │
               ▼
mart_variance_analysis
               │
               ▼
Power BI
```

Purpose:

```text
Budget vs Actual
Forecast vs Actual
Variance analysis
FP&A reporting
Executive planning
```

---

### CRM to Billing Reconciliation Flow

```text
crm_opportunities
        │
        │
        ▼
mart_pipeline_to_billing_reconciliation
        ▲
        │
fct_subscriptions
```

Purpose:

```text
Identify closed-won deals that have not reached billing
Detect delayed provisioning
Identify contract value mismatches
Identify start date mismatches
Support Revenue Operations controls
```

---

### Governance & Control Flow

```text
dbt Tests
        │
Source Freshness Checks
        │
Reconciliation Checks
        │
FX Validation Checks
        │
Data Quality Controls
        │
        ▼
mart_control_tower
        │
        ▼
Power BI Control Tower
```

Purpose:

```text
Data quality monitoring
Auditability
Finance controls
Operational trust
Executive confidence
```

---

## 12. Data Model Summary

The Finance Intelligence Platform uses a modern layered warehouse architecture built around:

```text
Dimensions
        +
Operational Facts
        ↓
Analytical Marts
        ↓
Forecasting
        ↓
AI Commentary
        ↓
Power BI Executive Reporting
```

Key characteristics of the model:

* Star-schema dimensional design
* Clear separation between transactional data and business metrics
* Support for SaaS-specific reporting
* Multi-currency reporting with GBP consolidation
* Acquisition-aware customer modelling
* Monthly recurring revenue ledger design
* Governance and control reporting
* Forecast-ready architecture
* AI-ready semantic layer

The model is intentionally designed to simulate a real-world finance analytics platform rather than a traditional reporting project.
