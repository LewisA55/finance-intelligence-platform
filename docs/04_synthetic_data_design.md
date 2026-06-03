Finance Intelligence Platform — Synthetic Data Design
This document details the business logic, financial distributions, behavioral assumptions, and anomalies used to simulate Nexus Technologies. These specifications drive the data generation scripts to ensure the synthetic dataset behaves like a realistic global enterprise SaaS business rather than a collection of random values.  
+ 1

## 1. Company Profile & Macro Growth Targets
Nexus Technologies is a mid-sized global SaaS enterprise scaling through organic market expansion and strategic M&A. The platform simulates a continuous 5-year timeline from January 1, 2022, to December 31, 2026.  
+ 1

### 1.1 Annual ARR Growth Constraints
To prevent unrealistic transactional volatility, subscription generation is bound by strict top-down annual ARR baseline targets:  

Fiscal Year	Target ARR Growth Rate	Core Strategic Narrative
2022	Baseline	
Initial market positioning; stabilization of core platform.  

2023	18% YoY	
Organic mid-market expansion in the UK and USA.  

2024	22% YoY	
Launch of Nexus AI; Acquisition of DataPulse Analytics in Q4.  

2025	25% YoY	
Legacy DataPulse migrations + high-velocity enterprise cross-sell.  

2026	17% YoY	
Market maturation; focus on retention and EBITDA margin optimization.  

### 1.2 Sales Transaction Seasonality
To mimic corporate buying behavior, new ARR booking dates are distributed unevenly throughout the fiscal year. Subscription activation engines apply a quarterly weighting constraint:  
+ 1

Quarter	Share of Annual New ARR	Operational Flavor
Q1	~20%	
Weakest Quarter  

Q2	~23%	
Steady build  

Q3	~27%	
Mid-year acceleration  

Q4	~30%	
Fiscal Close Spike  

## 2. Customer Structure & Tiering
The simulation maintains a conformed database of approximately 3,500 organic customers, expanded by an additional cohort via M&A. To mirror corporate reality, customer distribution follows an asymmetric 80/20 revenue value split.  
+ 1

### 2.1 Segment Distributions & ACV Boundaries
Customer Segment	Logo Share	Typical ACV Range	Core Operational Characteristics
Enterprise	
~5% (~175 Accounts)  

£150,000 – £750,000 / yr  

Multi-year annual contracts, low logo churn, complex procurement timelines.  

Mid-Market	
~25% (~875 Accounts)  

£30,000 – £70,000 / yr  

Standard annual contracts, moderate upgrades, regional sales ownership.  

SMB	
~70% (~2,450 Accounts)  

£5,000 – £15,000 / yr  

High-velocity monthly subscriptions, card-billing via Stripe, elevated churn risk.  

### 2.2 Revenue Concentration Risk (The Whale Distribution)
To satisfy the financial realisms monitored by corporate CFOs, revenue within the Enterprise tier is skewed to model concentration risk. The generation script enforces the following cumulative boundaries on total company ARR:  
+ 1

Metric	Target Revenue Ceiling
Top 10 Global Customers	
Account for approximately 15% of total ARR

  

Top 50 Global Customers	
Account for approximately 35% of total ARR

  

### 2.3 Industry & Regional Market Distributions
To ensure customer segment profiles don't default to uniform random distributions, the customer engine assigns industries and geographic footprints using strict enterprise market weights:  

Customer Industry Mix	Target Share	Regional Revenue / FX Exposure	Target Share
Technology / SaaS	
~30%  

United States (USD - $)	
~45%  

Financial Services	
~20%  

United Kingdom (GBP - £ Base)	
~25%  

Healthcare / Life Sciences	
~15%  

Germany / Europe (EUR - €)	
~20%  

Retail & E-commerce	
~15%  

Singapore (SGD - S$)	
~10%  

Manufacturing / Logistics	
~10%  

—	—
Professional Services / Other	
~10%  

—	—
### 2.4 Customer Cohort Start-Year Distribution
To populate the historical database and drive deep multi-year cohort retention curves, active and churned customers are assigned an initialization year based on a macro decay logic:  

Historical Cohort Group	Account Allocation Share	Analytical Value
Pre-2022 Cohort	Approximately 40%	
Establishes mature, long-term baseline customer records.  

2022 Cohort	Approximately 20%	
Trackable baseline for Year-1 vs. Year-2 net revenue retention.  

2023 Cohort	Approximately 20%	
Captures expansion velocity during mid-market push.  

2024 Cohort	Approximately 15%	
Captures pre-M&A organic client acquisition environment.  

2025 Cohort	Approximately 5%	
Focuses heavily on DataPulse cross-sell over standalone new logos.  

## 3. Product Structure & Revenue Mix
Nexus Technologies operates with an anchor product suite supplemented by a professional services division and an isolated legacy acquisition product line.  

### 3.1 Core Revenue & SKU Mix
Financial data generation enforces a target baseline distribution across the core ledger:  

Product / Stream	Revenue Mix Target	Pricing Architecture	Model Nature
Nexus Core	55%	
Per-Seat / Tiered Licence Fee  

Recurring Subscription  

Nexus Analytics	25%	
Add-on Premium Module Flat Fee  

Recurring Subscription  

Nexus AI	10%	
Usage-Based / Consumption Credit Bundles  

Recurring Subscription  

Professional Services	10%	
Fixed-Scope Implementation / SOW Fees  

One-Time Milestone  

### 3.2 Product Attachment Logic
Whenever a customer account is provisioned, their initial and expansion product bundles are bound by segment-specific attachment probabilities:  

Product Suite	Enterprise Attachment	Mid-Market Attachment	SMB Attachment
Nexus Core	
~95%  

~85%  

~75%  

Nexus Analytics	
~70%  

~35%  

~10%  

Nexus AI	
~45%  

~10%  

~2%  

### 3.3 Legacy Product Isolation (PulseEngine)
PulseEngine represents 100% of the historical revenue brought in by the DataPulse acquisition in October 2024. It is completely excluded from the core Nexus revenue mix at the time of ingestion.  
+ 1

From January 1, 2025, the simulation opens up a dedicated cross-sell/migration loop: approximately 65% of active PulseEngine accounts successfully migrate to the conformed Nexus Core/Analytics suites by year-end 2026, while the remaining 35% represent legacy churn or contraction.  

## 4. Subscription Behaviour & Event Engine
The simulation handles continuous contract states rather than simple static records. Every subscription record must transition through logical state changes to generate an auditable event log in fct_subscriptions.  
+ 1

### 4.1 Event State Rules
Event State	Business Trigger	Financial / Ledger Implications
New Business	
Initial contract creation.  

Triggers professional services invoice allocation (10% contract value baseline).  

Expansion / Upsell	
Secondary product module added or user seat count expanded.  

Incremental MRR increase logged with specific SKU tags.
Contraction / Downgrade	
Reduction in seat count or removal of an optional product module.  

Reduction in MRR without full customer churn.
Churn / Cancellation	
Full termination of the subscription relationship.  

Resets contract value to 0; flags account status as closed.
## 5. Churn & Retention Assumptions (NRR/GRR Targets)
To generate clean trends within mart_saas_metrics, the event engine applies different baseline churn rates by segment, reflecting the stability of enterprise revenue versus high-churn SMB cohorts:  

Customer Segment	Baseline Annual Logo Churn	Target Segment NRR	Behavioral Driver
Enterprise	
2% – 4%  

115%

  

High retention with aggressive AI credit expansion.  

Mid-Market	
6% – 8%  

102%

  

Stable core base with moderate module cross-selling.  

SMB	
12% – 16%  

85%

  

Elevated churn due to company liquidations and budget cuts.  

## 6. Acquisition Design (DataPulse Analytics)
To simulate structural data debt and post-merger integration challenges, the dataset introduces a non-organic growth event in late 2024.  

### 6.1 Acquisition Parameters
Parameter	Specification
Transaction Date	
October 1, 2024  

Target Entity	
DataPulse Analytics  

Primary Geography	
Germany (Transacted entirely in EUR)  

Acquired Metrics	
400 customer logos, £15m in active ARR  

Primary Legacy SKU	
PulseEngine

  

### 6.2 Data Quality Anomalies Injected at Ingestion
The extraction from the legacy DataPulse database introduces targeted anomalies to test Silver-layer cleansing macros:  

ID Mismatches: Approximately 20% of customer records use raw integer strings (4892) rather than standard alpha-numeric codes (CUST-1024).  

CRM Duplication: Approximately 10% of accounts exist as partial duplicates due to overlapping sales pipelines.  

Missing Metadata: Approximately 5% of records have null fields for industry classification.  

Taxonomy Chaos: Regions are logged using non-standard strings (e.g., "DE", "GER", "Deutschland") and products are labeled with internal legacy version codes.  

### 6.3 Post-Merger Migration Timeline (2025–2026)
65% Successful Migration: Accounts transition from PulseEngine to conformed Nexus Core + Analytics bundles, unlocking expansion ARR.  

35% Friction Cohort: Accounts experience contract contraction, legacy churn, or remain on the un-migrated product line through 2026.  

## 7. Employee & Organisational Structure
People represent the primary operating expense (OpEx) for a global SaaS business. This section governs payroll, headcount snapshots, and internal talent lifecycle events.  
+ 1

### 7.1 Target Headcount Scaling
To support the top-down revenue growth targets, the organization scales its total workforce across the 5-year timeline:  

2022	2023	2024	2025	2026
450 FTEs  

560 FTEs  

700 FTEs  

850 FTEs  

950 FTEs  

### 7.2 Functional Departmental Distribution
Headcount is allocated deterministically across functions to simulate realistic corporate cost weights:  

Functional Area	Headcount Allocation %	Primary Financial Treatment
Engineering / R&D	
~35%  

Operating Expense / Partially Capitalized  

Sales	
~20%  

Operating Expense / Commission-Driven  

Customer Success	
~15%  

Cost of Goods Sold (COGS) / Support Weight  

Product	
~10%  

Operating Expense  

Marketing	
~8%  

Operating Expense  

General & Administrative	
~7%  

Operating Expense  

Finance & HR	
~5%  

Operating Expense  

### 7.3 Salary Bands & Regional Cost Coefficients
Payroll calculations apply standardized salary bands adjusted by geography-specific market multipliers:  

Corporate Level	Base Salary Band	Region	Local Market Multiplier
Analyst	
£45,000 – £65,000  

United Kingdom	
1.00x baseline  

Manager	
£70,000 – £95,000  

United States	
1.45x market premium  

Senior Manager	
£100,000 – £130,000  

Germany	
1.05x localized rate  

Director	
£140,000 – £180,000  

Singapore	
1.20x regional rate  

VP	
£195,000 – £250,000  

—	—
### 7.4 Employee Lifecycle Event Engine
The generation script schedules transactional events to populate HR records with dynamic employee context:  

Hires & Terminations: Triggers immediate changes in active monthly FTE counts.  

Promotions & Transfers: Adjusts salary steps and changes departmental cost center tagging.  

### 7.5 Manager Hierarchy & Span of Control
Reporting lines are constructed dynamically across multiple hierarchy tiers:

The Org Chain: Individual Contributor (IC) → Manager → Senior Manager → Director → Vice President (VP).  

Injected Data Fault: To simulate operational HR data drift, approximately 5% of employee records are assigned a null manager ID. This forces the dbt cleaning layer to handle recursive trees to map reporting lines correctly.  
+ 1

### 7.6 Sales Headcount to Revenue Capacity Mapping
New ARR generation is strictly bounded by active Account Executive (AE) capacity and individual performance curves:  

Sales Tier AE	Target Annual ARR Capacity per Head	Ramping Timeline (Full Capacity)
Enterprise AE	
£1,500,000 – £2,500,000  

6 Months (50% capacity during ramp)  

Mid-Market AE	
£600,000 – £1,000,000  

3 Months (75% capacity during ramp)  

SMB AE	
£250,000 – £500,000  

1 Month (Immediate capacity)  

### 7.7 AE Quota Attainment & Variable Commission Logic
Attainment Curve: Quota performance mimics a corporate bell curve where average attainment sits at ~80%. Top performers (~15% of AEs) achieve 110%–130% of capacity; underperformers (~20% of AEs) hit only 30%–60%.  
+ 1

Variable Commission Cost Structure: Total cash compensation for Sales FTEs is computed as Base Salary + Commission Expense. The generation engine calculates Commission monthly, linking it directly to the volume of net-new ARR closed by that specific employee. This ensures that a massive booking quarter triggers a proportional spike in overall corporate Sales OpEx.  
+ 2

## 8. Operational Expense Structure & Profitability
Operating expenses (OpEx) and Cost of Goods Sold (COGS) are structured to reflect an enterprise scaling toward profitability.  

### 8.1 Core Cost Categories
Cost of Sales (COGS): Cloud infrastructure hosting, third-party integrated APIs (OpenAI token processing fees), and customer success contractors.  

Sales & Marketing: Core sales salaries, variable commission structures tied directly to new business ARR generation, advertising spend, and CRM software tooling.  

Research & Development: Developer payroll, internal testing environments, and localized equipment costs.  

General & Administrative: Rent for regional offices, legal retainers, corporate insurance, and Big Four annual audit fees.  

### 8.2 The EBITDA Maturity Curve
The financial transaction engine targets a progressive profitability trend line to reflect operational maturation:  

2022	2023	2024	2025	2026
8% EBITDA Margin  

10% EBITDA  

12% EBITDA  

15% EBITDA  

18% EBITDA  

### 8.3 SaaS Product Gross Margin Targets
To simulate modern AI SaaS operational realities, Cost of Goods Sold (COGS) allocations are distributed asymmetrically across product SKUs:  

Product Suite	Target Gross Margin	Primary COGS Driver
Nexus Core	
82%  

Standard multi-tenant database infrastructure.  

Nexus Analytics	
88%  

High margin; lightweight read-optimized analytical views.  

Nexus AI	
65%

  

Expensive variable workloads (OpenAI API tokens/GPU computing).

  

Professional Services	
35%  

Heavy direct human payroll cost (Nexus implementation consultants).  

The CFO Macro Narrative: Because Nexus AI is the fastest-growing revenue stream across 2024–2025, it acts as a dynamic structural weight that compresses overall corporate gross margin percentages despite total revenue increasing.  

## 9. Budget Design & Financial Bias
Budgets simulate an annual FP&A exercise where planning assumptions intentionally deviate from eventual operational actuals.  

### 9.1 Budgeting Philosophy
Budgets are static frameworks locked in November of the preceding fiscal year. Once approved, the base files remain immutable to preserve the baseline comparison layer.  
+ 1

### 9.2 Institutional Planning Bias (Variance Targets)
To prevent perfect actual-to-budget alignments, the planning script applies directional bias multipliers to the budget baselines:  

Revenue Budget: Programmed with an optimistic variance window of +/- 5%, creating scenarios where sales teams either hit unexpected windfalls or narrowly miss targets.  

Expense Budget: Subject to an underestimation factor of +/- 8%, simulating real-world departmental budget overruns.  

Headcount Budget: Models an aggressive vacancy-rate delay factor of +/- 10%, representing situations where hiring managers take longer to source talent than anticipated.  

### 9.3 Manual Excel Structure Deficiencies
The budget output replicates manual workbook formatting to test upstream ingestion cleaning layers:  

Injects multiple completely blank spacing rows between departmental tables.  

Incorporates hardcoded summary subtotal strings (e.g., "=== TOTAL OPEX ===").  

Embeds unformatted, inline textual commentary blocks and irregular multi-column structural alignments.  

### 9.4 Functional Departmental Bias Rules
Department	Injected Planning Error Profile	Behavioral Narrative
Sales	
+5% permanent optimism bias on revenue  

Consistently overestimating deal close probabilities in the CRM pipeline.  

Marketing	
+10% overestimation on lead velocity  

Creates a structural disconnect between pipeline forecasts and transactional billing.  

Engineering	
-8% underestimation on hiring & infra scaling  

Drives routine operational cost overruns as platform scale grows.  

G&A	
-5% blindspot on localized inflationary pressures  

Results in unbudgeted legal, compliance, and regulatory fee spikes.  

## 10. Forecast Design & Rolling Adjustments
Unlike static annual budgets, forecasts simulate dynamic, rolling monthly or quarterly outlooks that adapt to real-time performance trends.  

### 10.1 Pacing & Convergence Logic
As a fiscal year progresses, rolling forecasts incorporate historical actuals to continuously tighten predictive accuracy. The simulation enforces a strict variance narrowing structure:  
+ 1

[Q1 Forecast (Max Variance)]⟶[Q2 Forecast]⟶[Q3 Forecast]⟶[Q4 Forecast (Min Variance)]
### 10.2 Programmed Macroeconomic Forecast Shocks
To provide complex operational variance, the timeline experiences three explicit corporate disruption events:  

Q4 2024 — Early Acquisition Close: The DataPulse M&A transaction closes 60 days ahead of schedule. Financial actuals suddenly inherit 400 messy German customer contracts and localized operational costs that weren't factored into the prior forecast, creating massive temporary expense variances.  
+ 1

Q2 2025 — Nexus AI Demand Surge: The market adoption of the Nexus AI module exceeds expectations by 45%. While top-line revenue hits historic highs, variable computing COGS surge simultaneously, catching the FP&A team off-guard and squeezing the corporate Gross Margin % down.  
+ 1

Q1 2026 — Linked Whale-Loss Shock Event: The programmed Q1 2026 churn shock is mathematically bound to the Customer Concentration Model in Section 2.2. The engine selects a specific high-tier account from the Top 10 Global Customers pool—specifically an Enterprise account within the Financial Services vertical operating out of Germany (EUR). The termination event instantly wipes out exactly £650k of active ARR, triggering a localized contract termination log in fct_subscriptions, an immediate write-off journal in fct_expense, and an automated commentary trigger inside the rolling forecast models.  
+ 2

## 11. Multi-Currency & FX Behaviour
### 11.1 Currency Blueprint
Consolidation Group Currency: GBP (£)  

Localized Operating Currencies: USD (),EUR(€),SGD(S)  

### 11.2 Macroeconomic Exchange Rate Trends & Injected Shocks
Exchange rates are computed via deterministic trend paths matching real corporate macro conditions rather than random distributions:  

The USD Vector: Experiences a continuous strengthening curve across 2024, inflating the nominal value of US mid-market and enterprise subscriptions when translated to base GBP.  

The EUR Vector & Q4 2024 Shock: Subject to a sharp -12% devaluation shock during Q4 2024 matching the exact timeline of the DataPulse acquisition. This forces a wide divergence between the Deal Model value used by corporate strategy and the Actual Consolidated Revenue logged by the accounting group.  
+ 1

The SGD Vector: Maintained as a low-volatility, highly stable baseline currency anchor.  

### 11.3 Realised vs. Unrealised FX Ledger Postings (Account 7900)
Realised Gain/Loss: Calculated whenever the system processes an invoice receipt where the spot rate differs from the initial billing date.  

Unrealised Gain/Loss: Computed automatically at the final day of the reporting month, revaluing all outstanding foreign-denominated open balances. Both events dump their offsetting journal entries directly into 7900 - Realised/Unrealised FX Gain/Loss.  
+ 1

## 12. Intentional Data Quality Defect Catalogue
To simulate a fragmented enterprise landscape, specific technical and structural data faults are systematically engineered into the raw Bronze layer extraction scripts. These anomalies provide direct validation test cases for the dbt Silver layer and the governance models inside mart_control_tower.  
+ 1

### 12.1 Customer Relationship Management (CRM) Defects
Entity Duplication: Approximately 10% of global accounts are injected with minor naming variations (e.g., "Acme Corp", "Acme Corp.", "Acme Corporation"), forcing the implementation of conformed deduplication keys.  

Orphan Pipelines: Approximately 3% of closed-won sales opportunities are deliberately generated without a valid corresponding operational billing ID, simulating pipeline-to-billing leakage.  

Classification Gaps: Approximately 5% of legacy accounts possess null entries inside the industry category field to validate default imputation rules.  

### 12.2 Invoicing & Billing Platform Defects
ID Formatting Disconnects: DataPulse legacy accounts retain integer-based customer IDs (4892) rather than the conformed Nexus alpha-numeric strings (CUST-1024), requiring a unified transformation mapping table.  

Provisioning Latency Gaps: Random intervals of 2 to 7 days are injected between a CRM opportunity "Closed-Won" timestamp and the actual Stripe contract activation date, testing operational processing SLAs.  

### 12.3 Enterprise Resource Planning (ERP) Ledger Defects
Unmapped Cost Centres: Approximately 2% of transaction records are posted with generic or obsolete departmental codes (999-UNKNOWN), testing the warehouse's error-catching fallback logic.  

Journal Redundancy: Minor duplicate entry loops are introduced into manual adjustments to test the idempotent constraints of staging models.  

### 12.4 Human Resources Information System (HRIS) Defects
Broken Management Lines: Exactly 5% of active employee rows are generated with null manager keys, simulating data decay and testing recursive organization hierarchy models.  

Taxonomy Discrepancies: Department names from regional acquisitions use non-standard naming schemas (e.g., "Dev", "R&D", "Software Engineering"), which must be resolved into a clean, conformed functional dimension.  

## 13. Controlled Synthetic Generation Target Volumes
To ensure optimal execution speeds within a local DuckDB framework while providing a structurally rich asset dataset, target generation boundaries are locked:  

Targeted Target Asset Dataset	Minimum Row Baseline	Upper Target Boundary
Unique Customer Records	3,500	
3,900  

Total Global Employee Pool	850	
950  

Subscription Event Entries	8,000	
10,000  

Individual Invoiced Line Items	250,000	
350,000  

General Ledger GL Transactions	120,000	
180,000  

Budget Matrix Planning Rows	10,000	
20,000  

Rolling Forecast Structural Rows	15,000	
25,000  

Expanded Monthly MRR Ledger Rows	400,000	
700,000  