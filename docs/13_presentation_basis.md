# Phase 9 - CFO Presentation Basis

Project Atlas generates deliberately imperfect source data so the control
layer has real problems to catch. That created a tension: the same synthetic
defects were doing two jobs at once — proving the audit layer works *and*
powering CFO-facing views. Audit telemetry was presenting the numbers, so the
product could read as broken rather than governed.

The presentation basis separates the two jobs, the same way management
accounts sit on an adjusted basis above the raw ledger:

- **As-found basis** — the warehouse as loaded, defects included. This is what
  controls, audit checks and the Control Tower operate on. Nothing is cleaned
  away.
- **Presented basis** — what CFO surfaces should show: validated records,
  materiality-aware flags, coverage-aware series, proxy substitutions where
  the ledger has not closed. Every difference from as-found is carried as an
  explicit adjustment with a policy key and disclosure text.

## Policy as code

The rules live in the `presentation_policy` seed — a committed register, not
scattered constants:

| Policy | Rule |
| --- | --- |
| `source_completeness_expense` | Expense lines with a favourable variance, budget ≥ £100K and captured actuals below 20% of budget are missing capture, not underspend: excluded from presentation. |
| `variance_materiality` | A variance matters when it exceeds the greater of £50K and 0.5% of its measure. |
| `trailing_partial_clip` | A final period collapsing below 70% of the prior period is a boundary artifact: clipped. |
| `timing_lag_disclosure` | Collection measures lag billings by design: presented with disclosure. |
| `operational_opex_proxy` | Ahead of GL close, opex is presented on the operational proxy (payroll + AP spend) — the same basis the Excel workbook models. |
| `workforce_ghost_disclosure` | Payroll includes HRIS ghost-flagged records: an accepted limitation, disclosed. |

The React portal consumes these presented marts directly for CFO-facing views.
As-found values remain available one click away for governance review; the seed
is the source of truth for the disclosed presentation policy.

## Gold presentation surfaces

| Model | Grain | Purpose |
| --- | --- | --- |
| `mart_cfo_presented_financials` | posting period × department × account (FC_BASE_CASE) | Every line carries `as_found_actual_gbp`, `presented_actual_gbp`, `adjustment_amount_gbp`, `excluded_from_presentation_flag`, `presentation_basis_status`, `disclosure_text` and the governing `policy_key`. |
| `mart_cfo_presented_operating_metrics` | reporting month × metric (long format) | Ten CFO metrics (revenue, billings, collections, ARR, NRR, opex, operating profit, payroll, FTE) with as-found and presented values, proxy substitutions and disclosures. |
| `mart_cfo_metric_readiness` | metric | The reviewer registry: months presented vs excluded, true signal coverage windows (coalesced zeros are not coverage), applicable policies and status. |

## Verified behaviour (against the committed export snapshot)

- Mar 2026 presented financials exclude 8 expense lines (£320K of captured
  actuals against £3.3M of budget) — including "Marketing £12K actual vs
  £1.19M budget", which previously presented as Favourable.
- GL opex exists only for closed periods (Jan–Mar 2026). For the three closed
  months the operational proxy equals GL opex to the pound, so the presented
  opex/operating-profit series continues seamlessly on the proxy basis where
  the ledger stops — matching the Excel workbook's operating basis.
- Signal-based coverage windows: billings/collections from Jan 2023, workforce
  from Jan 2022, SaaS from Jan 2018, GL opex Q1 2026 only.

## What stays deliberately out of scope here

- The generator still produces *constant* defect rates. Making defects
  episodic (a migration spike that gets remediated, a bug that gets fixed) is
  the planned Phase 10 — it turns control telemetry into narrative.
- The portal should continue expanding the same pattern across new pages:
  presented basis by default, as-found basis inspectable, and every adjustment
  tied back to a policy key and disclosure.
