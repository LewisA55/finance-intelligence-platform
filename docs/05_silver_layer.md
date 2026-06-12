# Silver Layer

The Silver layer is the dbt staging and control boundary.

Silver models consume Bronze sources and expose source-aligned views with consistent typing, naming, boolean handling, dates, and control fields.

## Purpose

Silver is responsible for:

- reading from declared Bronze sources;
- casting raw fields into usable types;
- standardising dates, booleans, IDs, currencies, and numeric measures;
- preserving source-aligned grain;
- carrying lineage fields forward where useful;
- exposing clean inputs for Gold dimensions and facts.

Silver does not own enterprise KPI definitions or executive reporting logic. Those belong in Gold.

## Naming Convention

Silver model names follow:

```text
stg_<source_domain>__<source_entity>
```

Examples:

- `stg_billing__billing_invoices`
- `stg_procurement__vendor_payments`
- `stg_revenue__revenue_recognition_schedule`
- `stg_workforce__payroll_expense_lines`

## Implemented Silver Domains

| Domain | Examples |
| --- | --- |
| Accounting | `stg_accounting__erp_gl_journal_lines`, `stg_accounting__trial_balance` |
| Billing | `stg_billing__billing_invoices`, `stg_billing__billing_payment_allocations` |
| HRIS | `stg_hris__hr_employees`, `stg_hris__hr_headcount_snapshot` |
| Planning | `stg_planning__budget_lines`, `stg_planning__forecast_lines` |
| Procurement | `stg_procurement__vendor_invoices`, `stg_procurement__ap_ageing_snapshot` |
| Revenue | `stg_revenue__revenue_recognition_schedule`, `stg_revenue__deferred_revenue_rollforward` |
| Workforce | `stg_workforce__employee_compensation`, `stg_workforce__payroll_expense_lines` |

## Materialisation

Silver models are materialised as views.

This keeps the layer transparent and avoids persisting intermediate business logic before conformance in Gold.

## Testing And Coverage

Silver models have adjacent `.yml` documentation and schema tests. Additional singular tests validate cross-source relationships, arithmetic checks, date validity, and source-specific business rules.

## Boundary Rule

Silver models should consume Bronze sources only. Gold models should consume Silver and other governed Gold models, not raw CSV files.
