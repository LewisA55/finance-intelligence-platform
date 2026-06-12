# Data Generation

Project Atlas uses Python scripts to generate synthetic finance and operational source extracts for Nexus Technologies.

The data is fictional and designed for portfolio/demo use. It intentionally includes realistic business complexity and data quality issues so the warehouse can demonstrate governance and controls.

## Source Domains

| Domain | Example outputs |
| --- | --- |
| Accounting | Chart of accounts, GL journal lines, trial balance, financial statement extracts, control findings. |
| Billing | Customers, subscriptions, invoices, invoice lines, payments, payment allocations, AR ageing. |
| Revenue | Revenue recognition schedule and deferred revenue rollforward. |
| Procurement | Vendors, vendor invoices, invoice lines, payments, AP ageing. |
| Workforce | Employee compensation, payroll expense lines, headcount snapshots, headcount plan. |
| HRIS | Employee master and headcount snapshots. |
| Planning | Budget versions, budget lines, forecast versions, forecast lines, variance source extracts. |
| Product | Product catalogue and price book. |
| Reference | Regions, departments, FX rates. |
| Governance | Source generation QA and inventory outputs. |

## Generation Principles

- Source files mimic operational extracts rather than idealised analytical tables.
- Business entities are linked across domains using source-system identifiers.
- Data volumes are large enough to exercise dbt transformations and tests locally.
- Faults are intentional where they support downstream validation and control examples.
- Planning and forecast data preserve version/scenario semantics.

## Intentional Defects

The synthetic layer includes controlled defects such as:

- inconsistent or missing operational keys;
- legacy DataPulse migration irregularities;
- control findings in finance source extracts;
- workforce ghost headcount and status mismatches;
- revenue and deferred revenue reconciliation pressure points;
- planning variance scenarios.

These are not accidental generator failures. They are designed to make the Silver and Gold control layers meaningful.

## Generation Commands

```bash
python scripts/generate_sources.py
python scripts/qa/source_generation_qa.py
python scripts/qa/source_inventory_check.py
```

## Output Policy

Generated raw data is written under `data/raw/` and ignored by Git. The repository tracks generation logic, not generated source files.
