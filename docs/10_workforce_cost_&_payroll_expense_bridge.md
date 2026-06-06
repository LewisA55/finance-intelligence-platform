# Phase 3K.1 Documentation Note

## Workforce Cost & Payroll Expense Bridge

**Status:** Confirmed, documented, and code-locked
**Component:** Phase 3K.1 — Workforce Cost Source Extracts

**Outputs:**

```text
data/raw/workforce/employee_compensation.csv
data/raw/workforce/payroll_expense_lines.csv
data/raw/workforce/headcount_plan.csv
```

---

## Purpose

Phase 3K.1 bridges the HRIS/headcount layer into finance-ready workforce cost source extracts.

The phase converts employee and headcount data into granular compensation lines, payroll expense aggregations, and a forward-looking headcount plan. These outputs provide the workforce cost foundation required for later budget, forecast, variance analysis, and CFO reporting phases.

The generator intentionally remains a workforce subledger layer at this stage. It does not mutate the locked ERP GL, Trial Balance, Financial Statement Extract, Financial Statement Controls, or Control Findings Register.

---

## Design Position

The workforce cost layer is treated as a source-system extract, not a GL posting layer.

This mirrors the staging pattern used elsewhere in Project Atlas:

```text
Operational subledger first
GL integration later, only once the source design is validated
```

For Phase 3K.1, payroll expense is mapped to:

```text
6100 — Payroll Expense
```

The generator deliberately avoids the `4000` account range because the established Chart of Accounts reserves that range for revenue accounts.

---

## Output Design

### 1. `employee_compensation.csv`

**Grain:**

```text
employee_id + posting_period + compensation_component
```

**Components:**

```text
BASE_SALARY
EMPLOYER_TAX
BENEFITS
BONUS_ACCRUAL
```

**Purpose:**

Acts as the HRIS compensation subledger. The component-based design supports granular auditability and avoids a flat, spreadsheet-style employee-month layout.

---

### 2. `payroll_expense_lines.csv`

**Grain:**

```text
posting_period + department_id + account_code + currency + cost_component
```

**Purpose:**

Aggregates individual employee compensation records into structured finance-ready payroll expense lines.

The extract ties directly back to `employee_compensation.csv` and is designed to support later budget, forecast, variance, and potential payroll-to-GL integration phases.

---

### 3. `headcount_plan.csv`

**Grain:**

```text
position_id
```

**Plan statuses:**

```text
ACTIVE
OPEN_BUDGETED
BACKFILL
```

**Purpose:**

Provides the forward-looking workforce capacity framework needed for planning and forecasting.

---

## Mandatory Review Results

The Phase 3K.1 review passed successfully.

```text
employee_compensation.csv rows: 153,456
payroll_expense_lines.csv rows: 7,460
headcount_plan.csv rows: 970
```

Primary key checks passed:

```text
Duplicate compensation_pk: 0
Duplicate compensation_line_id: 0
Duplicate payroll_expense_pk: 0
Duplicate payroll_expense_line_id: 0
Duplicate position_pk: 0
Duplicate position_id: 0
```

Compensation grain validation passed:

```text
Active headcount snapshot rows: 38,364
Expected compensation rows:    38,364 × 4 = 153,456
Actual compensation rows:      153,456
Missing employee-period rows:  0
Extra employee-period rows:    0
```

Payroll aggregation tie-out passed:

```text
Max local variance: £0.00
Max GBP variance:   £0.00
Mismatched groups:  0
```

Headcount plan reconciliation passed:

```text
Latest active headcount: 898
Active plan rows:       898
Difference:             0
```

---

## 1. Temporal Boundary Caveat — Future-Dated Workforce Run Rates

### Finding

The workforce expense output extends through:

```text
2026-12
```

This occurs because Phase 3K.1 inherits the timeline bounds of the upstream `hr_headcount_snapshot.csv`.

### Architecture Rule

This is structurally valid and mirrors real enterprise planning behaviour.

In corporate planning environments, headcount snapshots for the current fiscal year may contain future operational structures, known future starters, budgeted roles, or run-rate workforce assumptions.

Downstream transformation layers should separate actual and future workforce periods using a global reporting-period boundary.

Recommended logic:

```text
posting_period <= current_reporting_period
```

Rows at or before the current reporting period should be treated as actual workforce cost.

Rows after the current reporting period should be treated as run-rate workforce capacity or planning baseline data.

### Governance Position

This is not a generator defect. It is an intentional source-system characteristic that should be managed through downstream period-status logic.

---

## 2. Ghost Headcount Variance — Injected Audit Anomaly

### Finding

Exactly 10 ghost employees are actively generating compensation rows in the workforce subledger.

Current observed impact:

```text
Ghost employees: 10
Compensation rows linked to ghost employees: 1,716
```

### Architecture Rule

These records are intentionally retained as controlled workforce data-quality anomalies.

They create a realistic audit scenario where payroll or workforce cost exists for employees who may not reconcile cleanly to verified operational master data.

### Governance Position

The ghost headcount rows should remain live in the source layer.

When downstream dbt audit models are built, these rows should trigger control checks such as:

```text
Payroll cost without valid employee master record
Payroll cost without verified active employment status
Headcount cost mismatch between HRIS and workforce subledger
Department or manager lineage mismatch
```

This gives the downstream governance layer a concrete, traceable workforce-control issue to detect, classify, and report.

---

## Accepted Phase 3K.1 Position

Phase 3K.1 is accepted and lockable as a workforce source-system layer.

The phase successfully extends Project Atlas beyond accounting actuals and into workforce economics, while preserving the integrity of the locked accounting spine.

Future phases may decide whether to integrate payroll expense into the ERP GL, but that should only occur after the workforce subledger design has been locked and reviewed.
