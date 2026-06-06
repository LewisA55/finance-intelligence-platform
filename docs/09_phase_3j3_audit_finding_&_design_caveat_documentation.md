# Phase 3J.3 Audit Finding & Design Caveat Documentation

**Status:** Approved, logged, and frozen for Project Atlas portfolio narrative
**Component:** Phase 3J.3 — Financial Statement Control Summary Matrix
**Output:** `data/raw/accounting/financial_statement_controls.csv`

## Purpose

Phase 3J.3 converts critical financial control checks into a formal raw data artifact. Rather than leaving reconciliation results hidden in logs or terminal output, the project now exposes ledger health, financial statement integrity, and subledger tie-outs through a structured control summary table.

The control failures documented below are intentional retained findings. They are not generator errors. They represent realistic enterprise control exceptions that downstream dbt models, audit tests, and Power BI dashboards can detect, monitor, and explain.

---

## Finding 1 — AR Control Breakage Due to Ledger Multi-Currency Scope Limitation

### Root Cause

The Order-to-Cash billing engine issues customer invoices in six billing currencies:

```text
AUD, CAD, EUR, GBP, SGD, USD
```

However, the current v1 ERP General Ledger posting scope supports only four ledger currencies:

```text
GBP, USD, EUR, SGD
```

As a result, AUD and CAD customer subledger balances exist in the billing layer, but those currencies are not currently represented in the GL control account posting scope.

### Control Behaviour

The `AR_CONTROL_TIE_OUT_CHECK` compares:

```text
Trial Balance account 1100 Accounts Receivable
vs
Customer billing subledger open AR balance
```

For unsupported currencies, the customer subledger can retain open invoice balances while the ledger-side AR balance is zero or incomplete. This produces a control failure.

### Governance Stance

This remains classified as `FAIL`.

In a real enterprise environment, this would represent an operational finance risk: the business is transacting with international customers before the core ERP ledger design fully supports all billing currencies, cash accounts, tax treatment, and AR control account posting requirements.

Keeping this failure visible is valuable because it gives downstream analytics engineering and audit layers a realistic control exception to identify, classify, and monitor.

---

## Finding 2 — Deferred Revenue Subledger-to-Ledger Disconnect

### Root Cause

A variance of:

```text
£3,065,300.33
```

exists between:

```text
Trial Balance account 2100 Deferred Revenue
and
deferred_revenue_rollforward.csv closing deferred revenue balance
```

The Trial Balance reflects the journal lines posted into the synthetic ERP GL. The deferred revenue roll-forward reflects the operational schedule tracking revenue recognition and remaining deferred balances by period, currency, and revenue category.

The failed control indicates that the operational deferred revenue schedule and the GL control account are not fully aligned.

### Control Behaviour

The `DEFERRED_REVENUE_CONTROL_TIE_OUT_CHECK` compares:

```text
Trial Balance account 2100 × -1
vs
Deferred revenue roll-forward closing balance
```

The variance is retained as a failed control because the reconciliation does not tie to zero.

### Governance Stance

This remains classified as `FAIL`.

This is a realistic corporate control exception. In practice, finance teams frequently need to investigate timing differences, interface logic, revenue schedule rebuilds, posting rules, manual adjustments, or cut-off issues when deferred revenue subledgers do not reconcile cleanly to the GL.

Retaining this exception strengthens the Project Atlas portfolio narrative. It avoids a sterile, artificially perfect simulation and creates a concrete downstream data-quality problem for dbt tests, reconciliation models, audit dashboards, and CFO commentary to surface.

---

## Accepted v1 Design Position

The Phase 3J.3 control file is designed to expose control exceptions, not suppress them.

The following checks pass cleanly:

```text
GL_JOURNAL_BALANCE_CHECK
TRIAL_BALANCE_GBP_ZERO_CHECK
TRIAL_BALANCE_LOCAL_ZERO_CHECK
BALANCE_SHEET_EQUATION_CHECK
P_AND_L_NET_INCOME_CHECK
AP_CONTROL_TIE_OUT_CHECK
```

The following checks intentionally remain visible as failed controls:

```text
AR_CONTROL_TIE_OUT_CHECK
DEFERRED_REVENUE_CONTROL_TIE_OUT_CHECK
```

These failures are accepted as known v1 control findings and are retained for downstream governance, audit testing, and reporting analysis.
