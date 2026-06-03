# Finance Intelligence Platform — Architecture Design

## 1. Architecture Overview

Project Atlas is designed as a modern local analytics platform for Nexus Technologies, a fictional multinational SaaS company.

The platform simulates a realistic finance transformation programme where fragmented operational data is ingested, cleaned, modelled, tested, and delivered into executive reporting.

The architecture is intentionally designed to mimic a real-world finance data warehouse rather than a simple dashboard project.

```text
Synthetic Source Systems
        ↓
Raw CSV / Excel Exports
        ↓
Python Ingestion
        ↓
DuckDB Raw Landing Tables
        ↓
dbt Bronze Layer
        ↓
dbt Silver Layer
        ↓
dbt Gold Layer
        ↓
Parquet Exports
        ↓
Power BI Executive Reporting
```

Forecasting and AI commentary sit alongside the Gold layer:

```text
dbt Gold Finance Marts
        ↓
Python Forecasting
        ↓
Forecast Outputs
        ↓
Structured Variance Facts
        ↓
Controlled AI Commentary
        ↓
Power BI
```

The platform is local-first, portable, auditable, and portfolio-friendly.

---

## 2. Core Architecture Principles

The platform is built around five principles:

### 2.1 Source-System Realism

The project will generate synthetic data that behaves like messy operational data from real finance systems.

The goal is not to create perfect clean tables immediately, but to simulate the type of fragmented source exports that finance teams often work with.

### 2.2 Layered Warehouse Design

Data will move through clear warehouse layers:

* Raw
* Bronze
* Silver
* Gold
* Forecast
* Control

Each layer has a defined purpose and clear responsibility.

### 2.3 Trusted Finance Metrics

Core finance and SaaS KPIs will be calculated in the dbt Gold layer rather than being hidden inside Power BI.

This creates consistent definitions for metrics such as ARR, MRR, NRR, churn, CAC, LTV, EBITDA margin, and Rule of 40.

### 2.4 Governance and Auditability

The platform will include data quality tests, reconciliation checks, lineage documentation, and control outputs.

This ensures reported numbers can be traced back to source-system data.

### 2.5 Grounded AI Commentary

The AI layer will not invent explanations or calculate metrics independently.

AI commentary will be generated only from structured variance facts produced by the warehouse.

---

## 3. Source Systems

Nexus Technologies operates across the UK, USA, Germany, and Singapore. The platform will simulate several disconnected systems used across finance, sales, HR, and FP&A.

### 3.1 Billing Platform

The billing platform represents a SaaS subscription billing system similar to Stripe, Chargebee, or Zuora.

Purpose:

* Customer billing
* Subscriptions
* Invoices
* Invoice lines
* Discounts
* Refunds
* ARR and MRR movements

Raw files:

```text
billing_customers.csv
billing_subscriptions.csv
billing_invoices.csv
billing_invoice_lines.csv
```

Known messiness:

* Different customer ID formats by system
* Discounts treated differently by region
* Mixed currencies
* Annual subscriptions not naturally represented monthly
* Refunds and credit notes
* Legacy DataPulse customer IDs after acquisition

Downstream use:

* fct_revenue
* fct_subscriptions
* fct_mrr_ledger
* mart_saas_metrics
* dim_customer
* dim_product

---

### 3.2 CRM Platform

The CRM platform represents a system similar to Salesforce or HubSpot.

Purpose:

* Customer account ownership
* Sales opportunities
* Customer segment
* Industry
* Region
* Sales team attribution

Raw files:

```text
crm_accounts.csv
crm_opportunities.csv
```

Known messiness:

* Customer names not matching billing records
* Manually entered regions
* Duplicate accounts
* DataPulse legacy customer records
* Missing industry or segment classifications

Downstream use:

* dim_customer
* dim_region
* revenue segmentation
* CAC and LTV analysis
* customer cohort analysis

---

### 3.3 ERP / General Ledger System

The ERP system represents a finance system similar to NetSuite, Microsoft Dynamics, SAP, or Oracle.

Purpose:

* Expense actuals
* GL postings
* Vendors
* Cost centres
* Account codes
* Department-level spend

Raw files:

```text
erp_gl_transactions.csv
erp_vendors.csv
erp_chart_of_accounts.csv
```

Known messiness:

* Unmapped cost centres
* Inconsistent department names
* Duplicate journal postings
* Mixed currencies
* Manual journal descriptions
* Local reporting differences by region

Downstream use:

* fct_expense
* dim_department
* dim_account
* mart_finance_kpis
* mart_variance_analysis

---

### 3.4 HRIS

The HR system represents a platform similar to Workday, BambooHR, or HiBob.

Purpose:

* Employee records
* Departments
* Job levels
* Salary bands
* Joiners
* Leavers
* Regional headcount

Raw files:

```text
hr_employees.csv
hr_headcount_snapshot.csv
```

Known messiness:

* Department names differ from finance cost centres
* Missing leaver dates
* Null manager fields
* DataPulse employees migrated mid-year
* Inconsistent location naming

Downstream use:

* fct_headcount
* dim_department
* revenue per employee
* cost per employee
* headcount trend analysis

---

### 3.5 Budget Workbook

The budget workbook represents manual FP&A planning files.

Purpose:

* Department-level monthly budgets
* Revenue budgets
* Expense budgets
* Headcount plans
* Regional budget submissions

Raw files:

```text
budget_2024.xlsx
budget_2025.xlsx
budget_2026.xlsx
```

Known messiness:

* Manual Excel tabs
* Different department naming
* Local currencies
* Blank rows
* Subtotal rows
* Inconsistent account descriptions

Downstream use:

* fct_budget
* mart_variance_analysis
* finance KPI reporting

---

### 3.6 Forecast Workbook

The forecast workbook represents rolling FP&A forecast submissions.

Purpose:

* Quarterly forecast versions
* Latest estimate reporting
* Revenue forecast
* Expense forecast
* Headcount forecast

Raw files:

```text
forecast_q1_2026.xlsx
forecast_q2_2026.xlsx
forecast_q3_2026.xlsx
forecast_q4_2026.xlsx
```

Known messiness:

* Multiple forecast versions
* Late submissions
* Manual overrides
* Changing assumptions
* Department-level adjustments

Downstream use:

* fct_forecast
* forecast comparison
* AI commentary
* Power BI forecast pages

---

### 3.7 FX Rates Source

The FX source provides monthly exchange rates for group reporting.

Purpose:

* Convert local currency revenue and expenses into GBP
* Support reported and constant-currency analysis
* Isolate FX impact from underlying business performance

Raw files:

```text
exchange_rates_2022_2026.csv
```

Currencies:

```text
GBP
USD
EUR
SGD
```

Group reporting currency:

```text
GBP
```

Downstream use:

* fct_revenue
* fct_expense
* fct_budget
* fct_forecast
* constant currency reporting
* FX impact analysis

---

## 4. Local Storage Structure

The project will use a clear local folder structure.

```text
data/
├── raw/
│   ├── billing/
│   ├── crm/
│   ├── erp/
│   ├── hr/
│   ├── budget/
│   ├── forecast/
│   └── fx/
│
├── processed/
└── exports/
    └── gold/
```

Raw files are stored under `data/raw`.

Power BI-ready outputs are stored under `data/exports/gold`.

---

## 5. DuckDB Storage

DuckDB acts as the local analytical warehouse.

Database file:

```text
duckdb/finance_intelligence.duckdb
```

The DuckDB database will store:

* raw landing tables
* dbt transformed models
* gold marts
* forecast outputs
* control outputs

DuckDB is selected because it is lightweight, fast, local, SQL-based, and well suited to portfolio-grade analytical projects.

---

## 6. Warehouse Layers

### 6.1 Raw Layer

The raw layer stores data close to the source format.

Example tables:

```text
raw_billing_customers
raw_billing_subscriptions
raw_billing_invoices
raw_billing_invoice_lines
raw_crm_accounts
raw_crm_opportunities
raw_erp_gl_transactions
raw_hr_employees
raw_budget
raw_forecast
raw_exchange_rates
```

Purpose:

* Preserve source-system truth
* Avoid premature cleaning
* Support lineage and reconciliation
* Retain load metadata

The raw layer should include:

```text
source_file_name
loaded_at
source_system
```

---

### 6.2 Bronze Layer

The Bronze layer performs light technical standardisation.

Example models:

```text
brz_billing_customers
brz_billing_subscriptions
brz_billing_invoices
brz_crm_accounts
brz_erp_gl_transactions
brz_hr_employees
brz_budget
brz_forecast
brz_exchange_rates
```

Bronze responsibilities:

* Rename columns into consistent snake_case
* Cast data types
* Parse dates
* Standardise booleans and basic status fields
* Retain source metadata
* Avoid business-heavy transformations

Bronze does not resolve complex business logic.

---

### 6.3 Silver Layer

The Silver layer performs business cleaning, conformance, and standardisation.

Example models:

```text
slv_customers
slv_customer_identity_map
slv_products
slv_departments
slv_regions
slv_exchange_rates
slv_subscriptions
slv_gl_transactions
slv_employees
slv_budget
slv_forecast
```

Silver responsibilities:

* Resolve customer identity across Nexus and DataPulse
* Create a unified `global_customer_id`
* Map legacy DataPulse products
* Standardise departments and cost centres
* Convert currencies into GBP
* Remove or flag duplicate transactions
* Clean subscription statuses
* Standardise regions and countries
* Prepare conformed dimensions

---

### 6.4 Gold Layer

The Gold layer contains reporting-ready finance and SaaS marts.

Example models:

```text
dim_date
dim_customer
dim_product
dim_department
dim_region
dim_account
fct_revenue
fct_expense
fct_headcount
fct_budget
fct_forecast
fct_subscriptions
fct_mrr_ledger
mart_saas_metrics
mart_finance_kpis
mart_variance_analysis
mart_control_tower
```

Gold responsibilities:

* Provide Power BI-ready tables
* Define trusted finance and SaaS metrics
* Support budget vs actual reporting
* Support forecast vs actual reporting
* Calculate ARR, MRR, NRR, GRR, churn, CAC, LTV, EBITDA margin, and Rule of 40
* Provide control and governance outputs
* Support AI commentary inputs

---

## 7. Critical Design Decisions

### 7.1 Customer Identity Resolution

The 2024 DataPulse acquisition creates conflicting customer ID structures.

Example:

```text
Nexus customer_id: CUST-1024
DataPulse customer_id: 4892
```

The platform will create a customer identity mapping layer:

```text
slv_customer_identity_map
```

This produces:

```text
global_customer_id
```

The `global_customer_id` is used throughout the Gold layer to avoid duplicate customer reporting and incorrect churn calculations.

---

### 7.2 DataPulse Acquisition Logic

Nexus Technologies acquires DataPulse Analytics in 2024.

This acquisition creates realistic integration challenges:

* duplicate customer records
* inconsistent customer IDs
* different product naming
* different regional structures
* customer migration from legacy products
* potential confusion between migration and churn

The warehouse must distinguish between:

```text
true customer churn
product migration
expansion
contraction
duplicate records
```

This is especially important for NRR and customer retention reporting.

---

### 7.3 Product Mapping

Nexus products:

```text
Nexus Core
Nexus Analytics
Nexus AI
```

DataPulse legacy product:

```text
PulseEngine
```

Treatment:

* PulseEngine remains a legacy product line during 2024
* From 2025 onward, migrated customers may move to Nexus Analytics or Nexus Core
* Non-migrated cancellations are treated as true churn
* Migrated customers should not be incorrectly counted as lost customers

This supports accurate SaaS metric reporting.

---

### 7.4 Multi-Currency Reporting

Nexus operates in:

```text
UK
USA
Germany
Singapore
```

Source currencies:

```text
GBP
USD
EUR
SGD
```

Group reporting currency:

```text
GBP
```

Financial facts should include:

```text
local_amount
currency_code
fx_rate_to_gbp
amount_gbp
```

This supports:

* group reporting
* reported growth
* constant currency growth
* FX impact analysis

---

### 7.5 Date Spine

A master date table will be created for the full reporting period.

Date range:

```text
2022-01-01 to 2026-12-31
```

The date spine supports:

* monthly reporting
* quarterly reporting
* annual reporting
* subscription expansion into monthly records
* budget and forecast alignment
* time intelligence in Power BI

The main date dimension is:

```text
dim_date
```

---

### 7.6 Monthly MRR Ledger

SaaS subscriptions are continuous, but finance reporting is monthly.

The platform will create:

```text
fct_mrr_ledger
```

This model expands subscription records into monthly records using the date spine.

Example:

```text
Contract value: £120,000 annually
Start date: 2024-06-01
End date: 2025-05-31
Monthly MRR: £10,000
```

Ledger output:

```text
2024-06-30: £10,000
2024-07-31: £10,000
...
2025-05-31: £10,000
```

This model supports:

* MRR
* ARR
* NRR
* GRR
* churn
* expansion
* contraction
* migration tracking

---

### 7.7 AI Commentary Guardrails

The AI commentary layer is intentionally constrained.

The AI layer will not calculate finance metrics directly.

Instead:

```text
Gold marts
        ↓
Structured variance facts
        ↓
Controlled AI prompt
        ↓
Executive commentary
```

The AI will only summarise validated warehouse outputs.

This reduces hallucination risk and makes commentary easier to review, test, and explain.

---

### 7.8 Power BI Consumption Method

The preferred consumption method is:

```text
dbt Gold models
        ↓
Parquet exports
        ↓
Power BI
```

This avoids server infrastructure and keeps the project portable.

Alternative:

```text
Power BI → DuckDB ODBC connection
```

However, Parquet exports are preferred for this portfolio project because they are fast, simple, and easy to version/document.

---

## 8. SaaS Metrics Architecture

The platform will calculate SaaS metrics in the Gold layer.

Key metrics:

```text
ARR
MRR
NRR
GRR
churn_rate
expansion_arr
contraction_arr
cac
ltv
cac_payback
rule_of_40
```

### 8.1 NRR

Net Revenue Retention measures how existing customer revenue changes over time.

Simplified logic:

```text
NRR =
(Opening ARR + Expansion ARR - Contraction ARR - Churned ARR)
/
Opening ARR
```

This requires:

* customer-level opening ARR
* expansion tracking
* contraction tracking
* churn tracking
* migration logic
* consistent customer identity mapping

Primary models:

```text
fct_subscriptions
fct_mrr_ledger
mart_saas_metrics
```

---

### 8.2 Rule of 40

Rule of 40 combines growth and profitability.

```text
Rule of 40 = Revenue Growth % + EBITDA Margin %
```

This requires:

* revenue growth from revenue models
* EBITDA margin from finance KPI models
* consistent reporting periods
* consistent GBP reporting

Primary models:

```text
mart_saas_metrics
mart_finance_kpis
```

---

### 8.3 CAC and LTV

CAC and LTV require revenue, customer, and spend alignment.

CAC requires:

* sales and marketing expense
* new customer acquisition volume
* reporting period

LTV requires:

* customer revenue
* gross margin
* churn behaviour or average customer life

Primary models:

```text
fct_expense
fct_revenue
dim_customer
mart_saas_metrics
```

---

## 9. Forecasting Architecture

Forecasting will be performed in Python using Gold layer outputs.

Flow:

```text
Gold finance marts
        ↓
Python forecasting script
        ↓
Forecast output table
        ↓
DuckDB / Parquet
        ↓
Power BI
```

Potential forecast outputs:

```text
forecast_revenue
forecast_expense
forecast_headcount
forecast_ebitda
```

Forecast outputs should include:

```text
forecast_period
metric_name
forecast_value
lower_confidence_bound
upper_confidence_bound
model_name
run_timestamp
```

Forecasts should be written back into the analytics layer rather than existing only inside notebooks.

---

## 10. AI Commentary Architecture

The AI commentary layer will generate narrative summaries from structured warehouse outputs.

Flow:

```text
mart_variance_analysis
mart_saas_metrics
mart_finance_kpis
forecast outputs
        ↓
Structured JSON / table of facts
        ↓
AI prompt
        ↓
Commentary output
        ↓
Power BI
```

The commentary output should include:

```text
commentary_id
reporting_period
audience
commentary_type
source_metric
generated_commentary
generated_at
```

The AI layer should be positioned as a summarisation and decision-support layer, not a calculation engine.

---

## 11. Governance and Control Architecture

The platform will include a finance data control layer.

Control areas:

* source freshness
* null key checks
* duplicate record checks
* invalid currency checks
* unmapped department checks
* unmapped customer checks
* FX conversion validation
* source-to-warehouse reconciliation
* budget completeness checks
* forecast version checks

Control output model:

```text
mart_control_tower
```

Example fields:

```text
control_id
control_name
control_category
status
severity
failed_record_count
last_run_at
owner
```

This model supports a Power BI Control Tower page showing whether the finance platform can be trusted.

---

## 12. Power BI Reporting Architecture

Power BI will consume Gold-layer Parquet outputs.

Planned report pages:

```text
Executive Overview
SaaS Metrics
Revenue Performance
Expense and Margin
Headcount
Forecasting
Control Tower
```

### 12.1 Executive Overview

Purpose:

* CFO-level performance summary
* revenue, margin, EBITDA, ARR, forecast position
* key risks and opportunities

### 12.2 SaaS Metrics

Purpose:

* ARR
* MRR
* NRR
* GRR
* churn
* expansion
* contraction
* Rule of 40

### 12.3 Revenue Performance

Purpose:

* revenue by region
* revenue by product
* revenue by customer segment
* actual vs budget
* actual vs forecast

### 12.4 Expense and Margin

Purpose:

* spend by department
* budget variance
* EBITDA bridge
* margin trend

### 12.5 Headcount

Purpose:

* headcount by department
* headcount cost
* revenue per employee
* cost per employee

### 12.6 Forecasting

Purpose:

* forecast trend
* confidence intervals
* forecast vs actual
* risk areas

### 12.7 Control Tower

Purpose:

* data quality status
* failed controls
* reconciliation checks
* source freshness
* auditability indicators

---

## 13. Target Project Structure

Local structure:

```text
finance-intelligence-platform/
│
├── README.md
├── .gitignore
│
├── docs/
│   ├── 01_project_charter.md
│   └── 02_architecture.md
│
├── data/
│   ├── raw/
│   │   ├── billing/
│   │   ├── crm/
│   │   ├── erp/
│   │   ├── hr/
│   │   ├── budget/
│   │   ├── forecast/
│   │   └── fx/
│   │
│   ├── processed/
│   └── exports/
│       └── gold/
│
├── duckdb/
│
├── dbt/
│
├── scripts/
│
├── notebooks/
│
├── powerbi/
│
└── assets/
```
