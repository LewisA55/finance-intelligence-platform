# Phase 3M.1 Documentation Note

## Forecast / Reforecast Scenario Generation

**Status:** Confirmed, reviewed, and code-lock ready
**Component:** Phase 3M.1 — Forecast / Reforecast Scenario Source Extracts

**Outputs:**

```text
data/raw/planning/forecast_versions.csv
data/raw/planning/forecast_lines.csv
```

---

## Purpose

Phase 3M.1 generates rolling forecast and reforecast source extracts for Nexus Technologies.

The forecast layer represents active corporate navigation after the Annual Operating Plan has been locked. It blends completed-month actuals with forward-looking scenario assumptions, creating a planning dataset that can support budget-vs-forecast, forecast-vs-actual, and scenario analysis.

---

## Forecast Versions

The generator creates three forecast scenarios:

```text
FC_BASE_CASE
FC_UPSIDE_CASE
FC_DOWNSIDE_CASE
```

Each version uses:

```text
Forecast year:   FY2026
Cutover period:  2026-03
Actual months:   2026-01 to 2026-03
Forecast months: 2026-04 to 2026-12
```

Completed months are treated as actuals and remain identical across all scenarios. Future months are scenario-driven.

---

## Grain

`forecast_lines.csv` mirrors the budget planning grain:

```text
forecast_version_code
posting_period
department_id
account_code
currency
planning_driver
```

This allows clean comparison between:

```text
Actual vs Budget
Actual vs Forecast
Budget vs Forecast
Base vs Upside vs Downside
```

---

## Actual Allocation Design Note

The financial statement extract does not carry native department-level actuals for all accounts.

To preserve comparability with the budget and forecast grain, completed-month non-payroll actuals are allocated back to the AOP grain using locked budget-line shares.

Payroll actuals are treated differently: they are sourced directly from `payroll_expense_lines.csv`, which already contains department, currency, and payroll component detail.

### Accepted Design Position

This is an intentional modelling bridge, not a source-data defect.

The allocation means that completed-month non-payroll actuals are departmentally distributed for planning comparability, but those departmental splits should be understood as budget-share allocations rather than native ERP departmental postings.

---

## Scenario Logic

Future-period forecasts apply deterministic scenario assumptions.

```text
Base Case:
- Revenue remains at 100% of the budget baseline.
- Payroll is reduced to 85% of budget.
- Marketing is reduced to 90% of budget.
- Hosting COGS reflects cloud infrastructure optimisation.

Upside Case:
- Revenue increases to 125% of budget.
- Payroll flexes upward to support demand.
- Marketing investment increases.
- Hosting costs scale with demand, with partial efficiency gains.

Downside Case:
- Revenue falls to 50% of budget.
- Payroll is reduced to reflect hiring restraint.
- Marketing spend is materially reduced.
- Hosting costs scale down with lower activity.
```

---

## Review Result

Phase 3M.1 passed mandatory review.

Key validation results:

```text
Forecast versions: 3
Forecast lines:    6,180
Duplicate grain:   0
Negative amounts:  0
```

Completed-month actual revenue ties to the financial statement extract:

```text
Financial Statement actual revenue, 2026-01 to 2026-03: £17,164,383.72
Forecast actual-period revenue captured:                £17,164,383.72
Variance:                                               £0.00
```

Payroll actuals tie to the workforce payroll extract:

```text
Payroll actual basis: £22,831,699.99
Forecast payroll:     £22,831,699.99
Variance:             £0.00
```

---

## Accepted Phase 3M.1 Position

Phase 3M.1 is accepted and lockable as a rolling forecast source layer.

The locked AOP remains untouched. The forecast layer provides management’s updated view of the year, blending actuals to date with forward-looking scenario assumptions.
