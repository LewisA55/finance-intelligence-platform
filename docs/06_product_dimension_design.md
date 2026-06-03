# Finance Intelligence Platform — Product Dimension Design

## 1. Purpose

This document defines the product hierarchy and SKU tracking structure used by Project Atlas.

The product dimension acts as a core reference table for subscription modelling, revenue generation, ARR/MRR reporting, product profitability, and DataPulse migration tracking.

The objective is to prevent downstream generators and reporting layers from treating all revenue as the same type of revenue.

This distinction is critical because:

* Recurring subscription products contribute to ARR and MRR.
* Usage-based products may contribute to recurring revenue but require separate margin treatment.
* Professional services revenue is one-time and must not pollute ARR or MRR.
* Legacy PulseEngine revenue must be isolated for acquisition migration analysis.

---

## 2. Product Hierarchy

The platform uses a three-level product hierarchy.

```text
Product Suite
    ↓
Product
    ↓
Billing SKU
```

### Product Suites

| Product Suite         | Description                                                |
| --------------------- | ---------------------------------------------------------- |
| Core                  | Main Nexus platform licence products                       |
| Analytics             | Premium analytics add-on products                          |
| AI                    | Usage-based AI and automation products                     |
| Professional Services | One-time implementation, training, and consulting services |
| Legacy                | Acquired DataPulse product line                            |

---

## 3. SKU Catalogue

| Product Suite         | Product Name            | SKU Code     | Category           | Recurring | Usage-Based | Legacy |
| --------------------- | ----------------------- | ------------ | ------------------ | --------- | ----------- | ------ |
| Core                  | Core Essentials         | CORE-ESS-001 | Subscription       | Yes       | No          | No     |
| Core                  | Core Professional       | CORE-PRO-001 | Subscription       | Yes       | No          | No     |
| Core                  | Core Enterprise         | CORE-ENT-001 | Subscription       | Yes       | No          | No     |
| Analytics             | Analytics Standard      | ANA-STD-001  | Subscription       | Yes       | No          | No     |
| Analytics             | Analytics Advanced      | ANA-ADV-001  | Subscription       | Yes       | No          | No     |
| Analytics             | Analytics Enterprise    | ANA-ENT-001  | Subscription       | Yes       | No          | No     |
| AI                    | AI Assist               | AI-AST-001   | Usage Subscription | Yes       | Yes         | No     |
| AI                    | AI Copilot              | AI-COP-001   | Usage Subscription | Yes       | Yes         | No     |
| AI                    | AI Enterprise           | AI-ENT-001   | Usage Subscription | Yes       | Yes         | No     |
| Professional Services | Implementation Services | PS-IMP-001   | One-Time Services  | No        | No          | No     |
| Professional Services | Training Services       | PS-TRN-001   | One-Time Services  | No        | No          | No     |
| Professional Services | Consulting Services     | PS-CON-001   | One-Time Services  | No        | No          | No     |
| Legacy                | PulseEngine Legacy      | PE-LEG-001   | Subscription       | Yes       | No          | Yes    |

---

## 4. Revenue Classification Rules

The product dimension must classify revenue correctly before subscription or invoice facts are generated.

### ARR / MRR Eligible

Products are ARR/MRR eligible when:

```text
is_recurring = true
```

and:

```text
product_category in ["Subscription", "Usage Subscription"]
```

Examples:

* Core Essentials
* Core Professional
* Core Enterprise
* Analytics Standard
* Analytics Advanced
* Analytics Enterprise
* AI Assist
* AI Copilot
* AI Enterprise
* PulseEngine Legacy

### ARR / MRR Excluded

Products are excluded from ARR/MRR when:

```text
is_recurring = false
```

Examples:

* Implementation Services
* Training Services
* Consulting Services

Professional services may appear in revenue and invoicing, but they must not contribute to ARR, MRR, NRR, GRR, or churn metrics.

---

## 5. Revenue Mix Targets

Revenue generation should align to the macro revenue mix defined in `business_rules.yaml`.

| Product Suite         | Target Revenue Mix |
| --------------------- | -----------------: |
| Core                  |                55% |
| Analytics             |                25% |
| AI                    |                10% |
| Professional Services |                10% |

PulseEngine is excluded from the standard Nexus product mix because it enters the business through the DataPulse acquisition.

---

## 6. Gross Margin Targets

Product gross margin assumptions support downstream product profitability and CFO reporting.

| Product Suite         | Target Gross Margin | Primary COGS Driver                              |
| --------------------- | ------------------: | ------------------------------------------------ |
| Core                  |                 82% | Standard multi-tenant infrastructure             |
| Analytics             |                 88% | Lightweight analytical workloads                 |
| AI                    |                 65% | Token usage, GPU/compute, external AI processing |
| Professional Services |                 35% | Implementation consultant payroll                |
| Legacy                |                 78% | Legacy DataPulse infrastructure                  |

---

## 7. DataPulse Migration Rules

PulseEngine is treated as a legacy acquired product.

| Attribute                    | Value               |
| ---------------------------- | ------------------- |
| Product Suite                | Legacy              |
| SKU Code                     | PE-LEG-001          |
| Acquisition Source           | DataPulse Analytics |
| Acquisition Date             | 2024-10-01          |
| Legacy Product Flag          | True                |
| Standard Nexus Mix Inclusion | False               |

From 2025 onward, selected PulseEngine customers migrate into Nexus Core and Nexus Analytics products.

The migration should be represented as a structured acquisition migration event, not as ordinary churn and unrelated new business.

This protects:

* Net Revenue Retention calculations
* acquisition integration reporting
* churn analysis
* customer lifecycle reporting

Expected migration pattern:

```text
PulseEngine Legacy
        ↓
Core Professional or Core Enterprise
        +
Analytics Advanced or Analytics Enterprise
```

---

## 8. Product Dimension Schema

The generated product catalogue should output:

```text
data/raw/products/product_catalog.csv
```

Expected grain:

```text
One row per billing SKU
```

Required columns:

| Column              | Description                                           |
| ------------------- | ----------------------------------------------------- |
| product_pk          | Stable surrogate key                                  |
| product_id          | Business product identifier                           |
| sku_code            | Billable SKU code                                     |
| product_name        | Product display name                                  |
| product_suite       | Product suite                                         |
| product_category    | Subscription / Usage Subscription / One-Time Services |
| revenue_mix_target  | Target revenue mix at product suite level             |
| gross_margin_target | Target gross margin                                   |
| is_recurring        | ARR/MRR eligibility flag                              |
| is_usage_based      | Usage-based billing flag                              |
| is_legacy_product   | Legacy acquisition flag                               |
| acquisition_source  | Source acquisition, if applicable                     |
| launch_date         | Product launch date                                   |
| retirement_date     | Optional retirement date                              |
| active_flag         | Current active product flag                           |

---

## 9. Generation Logic

The product generator should:

1. Load product rules from `business_rules.yaml`.
2. Expand high-level product suites into billable SKU rows.
3. Assign stable product primary keys.
4. Preserve revenue mix and gross margin assumptions.
5. Flag recurring, usage-based, service, and legacy products.
6. Write `product_catalog.csv` into `data/raw/products/`.
7. Validate uniqueness of `product_id` and `sku_code`.

Expected row count:

```text
13 rows
```

---

## 10. Downstream Dependencies

The product catalogue is required before generating:

* subscriptions
* invoices
* invoice lines
* revenue facts
* MRR ledger
* SaaS metrics
* product profitability analysis
* DataPulse migration events

This makes the product dimension a critical reference dataset for Phase 3 source generation.
