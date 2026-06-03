# Finance Intelligence Platform — Source System Generation Design

## 1. Purpose
This document defines the synthetic source systems that will be generated for Project Atlas. These datasets represent the raw operational exports received from business systems before any cleansing, standardisation, or modelling occurs. The objective is to simulate realistic enterprise source data that can be ingested into the Bronze layer of the Finance Intelligence Platform.

---

## 2. Source System Inventory & Ownership
The platform will generate seven primary source systems. The operational and data integrity responsibilities are mapped to the respective business functions below.

| Source System | Business Owner | Purpose | Primary Formats |
| :--- | :--- | :--- | :--- |
| CRM Platform | VP Sales | Customers, opportunities, account ownership | CSV |
| Billing Platform | Revenue Operations | Revenue, subscriptions, invoices | CSV |
| ERP Platform | Finance Controller | Expenses, journals, vendors, chart of accounts | CSV |
| HRIS Platform | People Team | Employees, salaries, organisational structure | CSV |
| Budget Platform | FP&A Team | Annual planning submissions | XLSX |
| Forecast Platform | FP&A Team | Rolling forecast versions | XLSX |
| FX Platform | Treasury Team | Monthly exchange rates | CSV |

---

## 3. Billing Platform
Business Owner: Revenue Operations
Files Generated: billing_customers.csv, billing_subscriptions.csv, billing_invoices.csv, billing_invoice_lines.csv

Purpose:
Represents a Stripe / Chargebee style subscription billing system.

Data Profile and Characteristics:
Primary Outputs: Customer records, active subscriptions, ARR/MRR events, invoice generation, and product billing.
Key Defects (Audit Traps): Legacy DataPulse customer IDs, localized currency variations, unlinked refund transactions, unmapped credit notes, and untracked subscription migrations.

Target Volumes:
| Dataset | Target Rows |
| :--- | :--- |
| billing_customers | 3,500 – 3,900 |
| billing_subscriptions | 8,000 – 10,000 |
| billing_invoices | 60,000 – 100,000 |
| billing_invoice_lines | 250,000 – 350,000 |

---

## 4. CRM Platform
Business Owner: VP Sales
Files Generated: crm_accounts.csv, crm_opportunities.csv

Purpose:
Represents Salesforce-style sales operations tracking the pre-revenue pipeline.

Data Profile and Characteristics:
Primary Outputs: Customer ownership, opportunity pipeline, closed-won deals, market segmentation, and industry classifications.
Key Defects (Audit Traps): Duplicate account records, missing industry tags, geographical region inconsistencies, and orphan opportunities trailing without parent accounts.

Target Volumes:
| Dataset | Target Rows |
| :--- | :--- |
| crm_accounts | 3,500 – 4,500 |
| crm_opportunities | 15,000 – 25,000 |

---

## 5. ERP Platform
Business Owner: Finance Controller
Files Generated: erp_gl_transactions.csv, erp_vendors.csv, erp_chart_of_accounts.csv

Purpose:
Represents NetSuite / Dynamics style financial ledger activity and core accounting records.

Data Profile and Characteristics:
Primary Outputs: Expense transactions, manual and automated journal entries, cost centres, vendor profiles, and chart of accounts structures.
Key Defects (Audit Traps): Duplicate journal postings, unmapped or legacy cost centres, department assignment inconsistencies, and transaction-to-ledger currency mismatches.

Target Volumes:
| Dataset | Target Rows |
| :--- | :--- |
| erp_gl_transactions | 120,000 – 180,000 |
| erp_vendors | 500 – 1,000 |
| erp_chart_of_accounts | 150 – 300 |

---

## 6. HRIS Platform
Business Owner: People Team
Files Generated: hr_employees.csv, hr_headcount_snapshot.csv

Purpose:
Represents Workday-style employee management and organizational structure tracking.

Data Profile and Characteristics:
Primary Outputs: Employee master records, baseline salary data, organisational hierarchy mapping, and historical joiners/leavers records.
Key Defects (Audit Traps): Null manager IDs breaking organizational rollups, missing termination dates for historical departures, and department naming variations across operational entities.

Target Volumes:
| Dataset | Target Rows |
| :--- | :--- |
| hr_employees | 850 – 950 |
| hr_headcount_snapshot | 20,000 – 50,000 |

---

## 7. Budget Platform
Business Owner: FP&A Team
Files Generated: budget_2024.xlsx, budget_2025.xlsx, budget_2026.xlsx

Purpose:
Represents annual FP&A corporate budget submissions, typically managed in un-sanitized spreadsheets.

Data Profile and Characteristics:
Primary Outputs: Departmental budget allocations, operational revenue plans, expense projections, and headcount growth models.
Key Defects (Audit Traps): Blank rows, hardcoded spreadsheet subtotals, embedded manual notes, and formatting inconsistencies between annual tabs.

---

## 8. Forecast Platform
Business Owner: FP&A Team
Files Generated: forecast_q1_2026.xlsx, forecast_q2_2026.xlsx, forecast_q3_2026.xlsx, forecast_q4_2026.xlsx

Purpose:
Represents intra-year rolling forecast adjustments used for active management decisions.

Data Profile and Characteristics:
Primary Outputs: Multiple rolling forecast versions, forecast convergence behavior models, and simulation of corporate forecast shock events like sudden top-tier customer churn.
Key Defects (Audit Traps): Manual executive overrides, un-reconciled version conflicts, and late-submission data disparities.

---

## 9. FX Platform
Business Owner: Treasury Team
Files Generated: exchange_rates_2022_2026.csv

Purpose:
Supports multi-entity group currency translation and consolidated reporting.

Data Profile and Characteristics:
Currencies Covered: GBP, USD, EUR, SGD.
Primary Outputs: Monthly average and month-end spot exchange rates.
Simulated Trends: EUR macroeconomic acquisition shock, a multi-year USD strengthening trend, and a stable SGD profile.

---

## 10. Generation Dependency Order
To ensure absolute relational integrity, downstream transaction data must reference pre-existing reference keys and exchange values. The scripts must generate source data in this strict linear sequence:

1. FX Rates (Provides currency conversion baseline scales)
2. Products (Establishes base SKU matrices)
3. Departments (Maps global functional cost entities)
4. Customers (Populates fundamental master records)
5. Employees (Sets up compensation hierarchies)
6. CRM Accounts (Maps sales ownership records)
7. Subscriptions (Drives operational contracts)
8. Invoices & Billing Events (Generates ledger revenue entries)
9. ERP (Records ledger financial adjustments)
10. Budgets (Maps corporate targets)
11. Forecasts (Projects dynamic intra-year trends)

---

## 11. Phase 3 Completion Criteria
The source system data generation phase is finalized only when the following thresholds are successfully met:

- [ ] **Code Execution:** All defined source files can be generated end-to-end via a master Python script without manual manipulation.
- [ ] **Volume Validation:** Row counts across all generated CSV and XLSX outputs fall squarely within the specified target ranges.
- [ ] **Defect Injection:** Intentional data anomalies and audit traps are verifiable in the raw files.
- [ ] **Business Scenario Validation:** The German M&A entity acquisition and subsequent multi-currency conversion impacts are accurately reflected.
- [ ] **Ingestion Readiness:** All outputs are formatted safely for zero-intervention automated loading directly into the DuckDB Bronze schema layers.