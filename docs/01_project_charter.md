# Project Charter: Project Atlas (Finance Intelligence Platform)

## 1. Executive Summary
Project Atlas is an enterprise data transformation and analytics engineering initiative for Nexus Technologies. The mandate of this project is to replace fragmented, siloed regional financial and operational reporting loops with a unified, automated, and auditable Finance Intelligence Platform. 

By modernizing the data stack using a local-first engineering framework (Python, DuckDB, dbt, and Power BI), Project Atlas establishes an immutable single source of truth for core software-as-a-service (SaaS) and corporate finance metrics. This platform eliminates manual spreadsheet reconciliation and provides the executive leadership team with trusted visibility into top-line growth, margin durability, budget-to-actual variance, and governance controls.

---

## 2. Business Problem & Context

### 2.1 Corporate Operating Profile
Nexus Technologies is a mid-sized global SaaS enterprise scaling through organic market expansion and strategic mergers and acquisitions (M&A). The business operates across a 5-year mature scaling horizon (2022–2026) under a strict corporate blueprint:
* **Functional Base Currency:** British Pound (GBP, £)
* **Regional Operational Footprint:** United States (USD), United Kingdom (GBP), Germany (EUR), and Singapore (SGD).
* **Core Product & SKU Mix:** Nexus Core (Licencing), Nexus Analytics (Premium Add-on), and Nexus AI (Usage-Based Consumption).
* **M&A Growth Event:** The Q4 2024 acquisition of DataPulse Analytics (Germany) introduced an isolated legacy product line (`PulseEngine`) and localized operational cost structures.

### 2.2 Core Operational & Reporting Challenges
Prior to Project Atlas, finance leadership faced structural barriers to executing data-driven strategic decisions due to acute fragmentation across the enterprise data lifecycle:

* **Siloed Systems & Data Fragmentation:** Critical financial and operational footprints are trapped inside disconnected transactional systems:
  * *CRM Platform (Salesforce):* Pipeline opportunities and account tier classifications.
  * *Billing Platform (Stripe):* Mid-market and SMB monthly subscription transactions.
  * *ERP Ledger (NetSuite):* General ledger accounting records and manual journals.
  * *HRIS (Workday):* Headcount snapshots, compensation structures, and management lines.
  * *Planning Environments:* Fragmented, manual Excel workbooks for annual Budgets and rolling Forecasts.
* **Pipeline-to-Billing Revenue Leakage:** Significant processing gaps exist between "Closed-Won" timestamps in the CRM and actual contract provisioning dates in the billing system, masking operational transaction latency and speed-to-revenue.
* **M&A Post-Merger Data Debt:** The ingestion of the DataPulse Analytics dataset introduced data chaos into the system, including mismatched account ID structures (integers vs. alphanumeric), legacy version codes, duplicate CRM records, missing industry metadata, and non-standard regional taxonomy labels (e.g., `"DE"`, `"GER"`, `"Deutschland"`).
* **SaaS Gross Margin Compression:** The explosive adoption of the consumption-heavy **Nexus AI** module features high variable infrastructure costs (OpenAI token processing fees and GPU compute workloads). Without precise product-level COGS allocation, visibility into overall gross margin compression is completely obscured.
* **Institutional Planning Biases:** Functional departments exhibit predictable budgeting errors (e.g., Sales over-optimism on pipeline close probabilities, Engineering underestimations of infrastructure scaling and hiring costs), generating massive actual-to-budget variances that manual sheets fail to capture dynamically.

---

## 3. Project Objectives

Project Atlas will engineer a local analytical workspace configured to achieve five primary breakthroughs:

* **Create a Governed Enterprise Data Foundation:** Consolidate data from all four distinct operational domains into a fast, portable analytics environment.
* **Standardize Enterprise SaaS Metrics:** Establish a unified semantic layer within dbt to compute complex subscription transformations uniformly, generating trusted metrics for ARR, MRR, NRR, GRR, Logo Churn, and the Rule of 40.
* **Automate FX Accounting & Group Consolidation:** Implement a robust multi-currency translation matrix converting USD, EUR, and SGD into group GBP, seamlessly isolating *Reported Currency* trends from *Constant Currency* performance.
* **Deliver a Finance Governance Control Tower:** Build a central operational monitoring center (`mart_control_tower`) that maps upstream data anomalies, catches duplicate journal entries, flags unmapped cost centers, and visualizes ledger health.
* **Deliver Guardrailed AI Executive Commentary:** Leverage statistical rolling forecasts and LLM pipelines to generate deterministic text-based financial summaries based exclusively on structured variance facts, removing the risk of data hallucinations.

---

## 4. Scope Boundary

### 4.1 In-Scope Components
* Processing and staging five years of multi-currency transactional data across the entire simulated corporate history (2022–2026).
* Development of an end-to-end ELT/BI pipeline executing a local modern data stack: **Python (Generation) $\rightarrow$ DuckDB (Storage) $\rightarrow$ dbt (Staging & Modeling) $\rightarrow$ Power BI (Presentation)**.
* Construction of a continuous monthly date spine ledger model to track historical customer retention cohorts and expansion vectors.
* Programming automated dbt schema tests, uniqueness assertions, and custom zero-balance financial ledger verification rules.
* Generating rolling quarterly forecasting iterations that narrow projection variances as the fiscal year matures.

### 4.2 Out-of-Scope Components
* Native integrations with live production software environments or cloud-data warehouse provisioning (e.g., Snowflake, BigQuery) during this local-first development sprint.
* Streaming or real-time data processing; the system architecture is optimized for stable, point-in-time snapshot processing and monthly operational close-out reporting loops.

---

## 5. Technology Stack & Architecture Design

The platform enforces a highly structured, modern data engineering lifecycle to ensure complete data lineage and transformation reproducibility:

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                        BRONZE Layer (DuckDB Landing)                    │
│   crm_opportunities  │  stripe_invoices  │  erp_ledger  │  hris_employees│
└─────────────────────────────────────┬───────────────────────────────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        SILVER Layer (dbt Cleansing)                     │
│    Deduplication   │   Taxonomy Alignment  │   Currency Standardisation │
└─────────────────────────────────────┬───────────────────────────────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        GOLD Layer (Dimensional Models)                  │
│       dim_customer   │   dim_employee   │   fct_mrr_ledger              │
└─────────────────────────────────────┬───────────────────────────────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        ANALYTICAL MART LAYERS                           │
│ mart_saas_metrics │ mart_variance_analysis │ mart_control_tower         │
└─────────────────────────────────────────────────────────────────────────┘

Core Pipeline Engine:

- **Python** is utilized for custom data synthesis, transactional generation algorithms, forecasting routines, and local file system orchestration.
- **DuckDB** serves as the embedded analytical database engine, providing high-performance vectorized SQL processing and local-first storage capabilities.

### Transformation & Governance

**dbt (Data Build Tool)** acts as the transformation and governance framework across multiple warehouse layers:

| Layer | Purpose |
|---------|---------|
| Bronze | Raw source ingestion and 1:1 schema enforcement |
| Silver | Data cleansing, deduplication, taxonomy alignment, and currency standardization |
| Gold | Dimensional modeling, fact tables, and business-ready datasets |
| Control Tower | Governance reporting, data quality monitoring, and reconciliation controls |

### Intelligence & Visualization

- **Python Analytical Suite** provides forecasting models, statistical analysis, and guardrailed AI commentary generation.
- **Power BI Desktop** consumes curated Gold-layer outputs and analytical marts to deliver executive dashboards and management reporting.

---

# 6. Project Success Criteria & Target Volumes

Project Atlas will be considered successful when all core datasets can be generated, transformed, governed, and visualized through the end-to-end analytics platform.

## Target Ingestion & Analytical Assets

| Dataset | Minimum Baseline | Upper Boundary |
|----------|----------|----------|
| Unique Conformed Customer Records | 3,500 | 3,900 |
| Total Global Employee Lifecycle Pool | 850 | 950 |
| Subscription Contract Event Entries | 8,000 | 10,000 |
| Individual Invoiced Line Items | 250,000 | 350,000 |
| General Ledger Transactions | 120,000 | 180,000 |
| Budget Planning Matrix Rows | 10,000 | 20,000 |
| Rolling Forecast Projection Rows | 15,000 | 25,000 |
| Monthly MRR Ledger Rows | 400,000 | 700,000 |

## 6.1 Engineering Quality Thresholds

### Pipeline Execution Speed

Target execution runtime under **60 seconds on standard local hardware** for the complete analytical workflow:

```text
Raw Sources
    ↓
DuckDB Landing
    ↓
dbt Transformation
    ↓
Analytical Marts
    ↓
Parquet Outputs
```

### Data Fault Resolution

All engineered defects contained within the **Intentional Data Quality Defect Catalogue** must be:

- Corrected
- Mapped
- Quarantined
- Surfaced through governance controls

The final semantic layer should remain trusted, auditable, and suitable for executive reporting.

### Ledger Reconciliation Integrity

The `mart_control_tower` must continuously validate:

- Zero-balance journal integrity
- Complete account mappings
- Complete cost centre mappings
- FX translation completeness
- Data quality control status

No unmapped cost centres or unresolved financial control failures should reach executive reporting layers.