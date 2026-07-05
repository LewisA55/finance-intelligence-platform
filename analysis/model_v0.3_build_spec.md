# Atlas Integrated Financial Model v0.3 — Build Specification

This is the execution runbook for rebuilding `atlas_integrated_financial_model_v0.21.xlsx`
into `v0.3`: a real, decision-grade three-statement model with a working balance sheet, plus a
fixed DCF and a populated outputs contract. Work from a **copy** of v0.21 (`Save As v0.3`
before making any changes) so the old workbook remains available for comparison.

Each phase below is independently checkable — do them in order, and confirm the phase's check
passes before moving to the next. All new formulas are given once, for the **first forecast
month column**; enter the formula in that column and fill right across the remaining forecast
months (standard practice — every forecast column uses the same relative formula).

Scope: all schedules are Company Total, monthly. **Three period regimes, each labelled in the
period-type header row of every statement sheet:**

| Regime | Months | Basis |
| --- | --- | --- |
| `Actual — pre-anchor` | Jan 2023 – Dec 2025 | Governed actuals feed (Phase 1): **income statement and working-capital lines only.** No balance sheet or cash flow statement exists before the anchor — those columns render blank/"n/a" (never zero), and the balance/cash checks read "n/a". |
| `Modelled Actual (bridge)` | Jan 2026 – Jun 2026 | Balance-sheet rollforward from the 31 Dec 2025 opening anchor: actual IS/working-capital movements + modelled PP&E/debt/tax movements (Phase 6a) |
| `Forecast` | Jul 2026 – Dec 2029 | Full assumption-driven schedules |

Two hard consequences of the anchor date, stated up front because both shape every later
phase:

1. **The integrated (balancing) three-statement region spans 1 Jan 2026 → Dec 2029 only.**
   The 31 Dec 2025 anchor is the earliest possible balance-sheet date — there are no
   cash/PP&E/debt/equity positions before it and no way to construct them. Pre-anchor months
   are calibration history and IS/working-capital display, and must never be presented as if
   the model balances there. The bridge (Phase 6a) then carries the anchor forward across the
   six months where actuals and the balance sheet overlap, so the forecast opens from a
   derived 30 Jun 2026 position rather than teleporting the December anchor forward.

2. **Anchor retained earnings deliberately do not reconcile to the pre-anchor P&L history —
   and the model must say so.** Cumulative proxy operating result Jan 2023 – Dec 2025 is
   **−£82.2m**, while the anchor carries retained earnings of **+£5.17m**. This is not an
   error: the historical series is an *operational proxy* (recognised revenue less
   payroll + AP spend), while the anchor is a *synthetic statutory* snapshot whose equity
   position reflects everything the proxy P&L does not capture (funding, capitalisation,
   statutory adjustments — none of which the platform models). Any reviewer who sums the
   history against the anchor will find an ~£87m gap within minutes; disclose it before they
   do. The retained-earnings rule, stated as three lines:

   - Retained earnings opening balance = the 31 Dec 2025 statutory anchor (£5,172,593.20)
   - Retained earnings movement = modelled net income from Jan 2026 onward only
   - Jan 2023 – Dec 2025 operating history is calibration evidence only — it never touches equity

   Required disclosures: a note row directly beneath Retained Earnings on `08_Forecast_BS`
   ("Anchor equity is statutory; pre-anchor P&L is an operational proxy — bases deliberately
   unreconciled, see 01_Model_Map"), and the fuller basis paragraph in `01_Model_Map`.

### Mechanical regime enforcement (build this before any schedule)

The regimes are enforced by machinery, not discipline. Three named control cells in
`02_Control` are the single source of truth for every date boundary in the workbook (and
they feed the `12_Outputs` technical fields directly):

| Named cell | Value | Feeds |
| --- | --- | --- |
| `anchor_date` | 2025-12-31 | opening balance sheet date, `data_as_of_date` basis |
| `actuals_cutoff` | 2026-06-30 | `actuals_cutoff_date` in 12_Outputs, bridge end |
| `forecast_start` | 2026-07-01 | `forecast_start_date` in 12_Outputs, forecast regime |

Every monthly model sheet (`05_Monthly_Model`, `07_Forecast_IS`, `08_Forecast_BS`,
`09_Forecast_CFS`) carries a three-row regime block under the existing Period/Period-Type
header rows, each cell a formula off the period date and the named cells — never typed
per column:

```
period_regime               = IF(X$4 > actuals_cutoff, "Forecast",
                               IF(X$4 > anchor_date, "Modelled Actual (bridge)",
                                "Actual - pre-anchor"))
is_integrated_model_period  = X$4 > anchor_date          → TRUE from Jan 2026
is_forecast_period          = X$4 >= forecast_start      → TRUE from Jul 2026
```

Formula conventions keyed to the flags (row references assume the flags land in rows 6–7;
adjust to wherever the block is inserted):

- Every balance-sheet and CFS formula wraps as `=IF(X$6, <calculation>, "n/a")` — the
  integrated-period flag, not a string compare, decides whether a statement exists.
- Every check row (balance check, cash reconciliation, rollforward/continuity checks) wraps
  the same way: `"n/a"` pre-anchor, a number from Jan 2026.
- Schedule logic that differs between bridge and forecast (e.g. actual vs assumption-driven
  revenue) keys on `is_forecast_period`.
- The existing `Period Type` row ("Actual"/"Forecast") stays for backward compatibility with
  the current `05`/`07` formulas, but all **new** logic keys on the flag rows.

`01_Model_Map` (currently an empty sheet) becomes the model's front door: the regime table
above, the three control dates, the sheet map, and the retained-earnings basis paragraph —
the "42 months of operating evidence, 6 months of actual integrated bridge, 42 months of
forecast" story in one place.

---

## Phase 1 — Replace the Power Query actuals feed

### What's changing and why

The old `04_Model_Feed_Final` tab ran 16 Power Query queries (7 raw domain imports → 7 monthly
rollups → 1 join) to reconstruct a 60-column table, of which only 29 columns were ever actually
used by any formula in the workbook. All of that logic — including the ad hoc payroll+AP opex
proxy and the 7 per-domain "control status" checks — now exists as one governed, tested dbt
model: `mart_model_actuals_feed_excel`.

**The new model deliberately emits the exact same status vocabulary the old Power Query
produced** ('OK' / 'Control Exception' / 'Check' / 'Minor Variance' / 'Definition Difference' /
'Source Definition Difference') — verified against the old workbook's own formulas. This means
**`11_Audit_Checks`'s 8 formulas need zero changes.** Only the data source changes.

### Source file

`analysis/exports/mart_model_actuals_feed_excel.csv` (42 rows, Jan 2023 – Jun 2026 — the same
span the workbook's own `11_Audit_Checks` already expects: "Expected 42 / Actual 42"). This is
a snapshot from the current warehouse; once you run `dbt build` yourself, regenerate it via the
Power BI export pipeline (`python scripts/exports/export_powerbi_views.py`) and re-point at
`data/exports/powerbi/csv/mart_model_actuals_feed_excel.csv` — same columns, same order.

Columns (29 + date, matching the old table exactly): `reporting_month_date`, `billings_gbp`,
`recognised_revenue_actual_gbp`, `cash_collected_gbp`, `open_ar_exposure_gbp`,
`closing_deferred_revenue_gbp`, `ap_invoice_spend_gbp`, `supplier_cash_paid_gbp`,
`open_ap_liability_gbp`, `payroll_cost_gbp`, `active_fte_count`, `headline_arr_gbp`,
`net_arr_delta_gbp`, `gross_revenue_retention_rate`, `net_revenue_retention_rate`,
`logo_churn_rate`, `revenue_per_active_fte_gbp`, `actual_operating_expense_gbp`,
`actual_operating_profit_gbp`, `actual_operating_margin`, `arr_bridge_variance_gbp`,
`arr_monthly_run_rate_variance_gbp`, `ap_control_status`, `deferred_revenue_model_status`,
`saas_arr_control_status`, `saas_retention_control_status`, `workforce_control_status`,
`arr_bridge_status`, `revenue_vs_o2c_billings_variance_gbp`, `revenue_vs_o2c_billings_status`.

### Steps

1. In Power Query Editor (`Data → Queries & Connections`), delete these 16 queries: `src_ap_working_capital_control`, `src_deferred_revenue_control`, `src_o2c_customer_collections`, `src_revenue_waterfall`, `src_saas_arr_movement`, `src_saas_retention`, `src_workforce_cost_control`, `pq_ap_monthly_actuals`, `pq_deferred_revenue_monthly_actuals`, `pq_o2c_monthly_actuals`, `pq_revenue_monthly_actuals`, `pq_saas_arr_monthly_actuals`, `pq_saas_retention_monthly_actuals`, `pq_workforce_monthly_actuals`, `pq_model_feed_final`, `pq_monthly_actuals_feed`.
2. `Data → Get Data → From File → From Text/CSV` → select `mart_model_actuals_feed_excel.csv`.
3. In the Power Query preview, set `reporting_month_date` to Date type (the rest auto-detect correctly). Close & Load **To** → Existing worksheet → `04_Model_Feed_Final!A1`, replacing the old table.
4. Rename the loaded table back to `tbl_model_feed_final` (Table Design → Table Name) so every structured reference in `05_Monthly_Model` and `11_Audit_Checks` resolves unchanged.
5. Delete the now-orphaned connections (`Data → Queries & Connections`, right-click → Delete) for anything still listed.
6. `Data → Refresh All`.

### Check

- `05_Monthly_Model`'s "Actual" columns show the same values as before the migration (spot-check 3-4 months against the pre-migration workbook).
- `11_Audit_Checks` shows the same pass/fail verdicts as before (Feed Integrity: Expected 42 / Actual 42 / OK; same control-exception counts).
- Power Query Editor shows zero queries.

---

## Phase 2 — New assumptions (`06_Assumptions`)

Add these rows to `tbl_assumptions`, following the existing pattern (Category, Driver,
Downside, Base, Upside, Selected Scenario formula `=CHOOSE(MATCH('02_Control'!$B$14,...))`).

**Also revise two existing rows** — the current Base-case growth assumptions were calibrated
before the presented-basis actuals existed and don't match the real trailing trend (checked
directly: trailing-12-month recognised revenue grew ~0.28%/month, ~3.3% annualised; presented
opex actually *declined* ~-0.35%/month over the same window):

| Category | Driver | Downside | Base | Upside | Note |
|---|---|---|---|---|---|
| Revenue & SaaS Growth | Recognised Revenue Growth % | 0.2% | **0.6%** *(was 1.0%)* | 1.0% | Base assumes modest reacceleration from the ~0.3%/month trailing trend |
| Operating Cost Drivers | Payroll Growth % | 0.3% | **-0.4%** *(was 1.0%)* | -0.8% | Matches the trailing-12-month actual decline; the dominant opex lever (~94% of opex) |
| Operating Cost Drivers | AP Spend Growth % | 0.2% | **-0.2%** *(was 0.8%)* | -0.5% | Minor weight (~6% of opex) but directionally consistent |

New rows:

| Category | Driver | Downside | Base | Upside | Note |
|---|---|---|---|---|---|
| Capital Expenditure | Capex % of Revenue | 2.0% | 3.0% | 4.0% | Monthly capex as % of that month's recognised revenue |
| Capital Expenditure | Existing PP&E Remaining Useful Life (months) | 60 | 60 | 60 | Depreciates opening net PP&E (£6.4m) to zero on a straight line |
| Capital Expenditure | New Capex Useful Life (months) | 48 | 48 | 48 | Each month's capex depreciated separately over this life |
| Debt | Interest Rate (annual) | 8.0% | 6.5% | 5.5% | Applied monthly as rate/12 on average balance |
| Debt | Scheduled Monthly Repayment | £50,000 | £75,000 | £100,000 | Fixed amortisation; skipped if it would breach minimum cash |
| Debt | Minimum Cash Threshold | £5,000,000 | £3,000,000 | £2,000,000 | Draw trigger — see Phase 5 |
| Debt | Cash Sweep Switch | 0 | 0 | 0 | 0 = off (default), 1 = on. Off means excess cash is not used to prepay debt early |
| Tax | Opening Tax-Loss Carryforward | £0 | £0 | £0 | Assumption, not derived — the opening BS carries no such line item |
| DCF Drivers | Target Operating Margin (long-run) | 5% | 12% | 18% | The glide-path target the Base case reaches by the end of the explicit forecast (Dec 2029) |
| Circularity | Circularity Breaker | 0 | 0 | 0 | 1 = zero out interest expense for one recalculation pass, to unstick a broken iterative calc |

### Iterative calculation: deliberately NOT required

The debt schedule is designed to solve acyclically (draw decisions sized on pre-interest cash
with an opening-balance interest buffer — see Phase 5), so **leave iterative calculation off**.
This is a feature: if a future edit introduces a genuine circular reference, Excel will warn
loudly instead of silently converging to something nobody reviewed. Document in `02_Control`:
"Iterative Calculation" = "Off — debt circularity resolved algebraically (Phase 5 convention)".
The Circularity Breaker assumption remains as a recovery tool only.

---

## Phase 3 — Income statement to Net Income (`07_Forecast_IS`)

Existing rows (Recognised Revenue, Payroll Cost, AP/Vendor Spend, Operating Expense Proxy,
Operating Profit, Operating Margin) are unchanged in mechanism — they still grow off the
(now-recalibrated) assumptions. Add four new rows below Operating Profit, first forecast
column:

```
Depreciation & Amortisation   = <PP&E schedule Total D&A this month>      (Phase 4)
EBIT                          = Operating Profit - D&A
Interest Expense              = <Debt schedule Interest Expense>          (Phase 5)
Profit Before Tax             = EBIT - Interest Expense
Tax Expense                   = <Tax schedule Current Tax Expense>        (Phase 6)
Net Income                    = Profit Before Tax - Tax Expense
```

Historical (Actual) columns: D&A, Interest Expense and Tax Expense are `0` for history (the
opening BS anchor already nets these effects into retained earnings up to Dec 2025; the
schedules only run forward from the forecast start) — so historical EBIT/PBT/Net Income equal
historical Operating Profit. Key the switch on the regime flags (`=IF(X$6, <schedule ref>, 0)`
for the D&A/interest/tax rows — integrated periods use the schedules, pre-anchor months are 0
on the IS since these lines only exist from Jan 2026), consistent with the `IF($X$5="Actual",...)` pattern
already used throughout `05_Monthly_Model`.

**Check**: for every historical month, Net Income = Operating Profit (D&A/Interest/Tax are 0).

---

## Phase 4 — PP&E schedule

New section on `08_Forecast_BS`, above the existing Working Capital Assets section:

```
Opening Gross PP&E            = <prior month Closing Gross PP&E>; first bridge month (Jan 2026) = £8,500,000 (mart_opening_balance_sheet.ppe_gbp)
Capex                         = Capex % of Revenue × Recognised Revenue (this month)
Closing Gross PP&E            = Opening Gross PP&E + Capex

Opening Accumulated Depreciation = <prior month Closing>; first bridge month (Jan 2026) = £2,100,000 (abs of mart_opening_balance_sheet.accumulated_depreciation_gbp)
Depreciation - Existing PP&E  = Opening Net PP&E at forecast start (£6,400,000) / Existing PP&E Remaining Useful Life
                                 (constant £ amount each month until the existing base is fully depreciated, then 0)
Depreciation - New Capex      = SUMPRODUCT of each prior month's Capex / New Capex Useful Life,
                                 for every capex vintage still within its useful life
                                 (i.e. this month's capex starts depreciating next month)
Total Depreciation            = Depreciation - Existing PP&E + Depreciation - New Capex
Closing Accumulated Depreciation = Opening Accumulated Depreciation + Total Depreciation

Closing Net PP&E              = Closing Gross PP&E - Closing Accumulated Depreciation
PP&E Rollforward Check        = Closing Net PP&E - (Opening Net PP&E + Capex - Total Depreciation)   [must = 0]
```

`Total Depreciation` here is the `D&A` figure Phase 3 pulls into the income statement.

**Depreciation - New Capex** is the one row needing a small helper: track each forecast
month's capex in its own row (already present as `Capex` above), then for month *t*:
`= SUM of (Capex in month k) / New Capex Useful Life, for every k <= t where t - k < New Capex Useful Life`.
In Excel this is a `SUMPRODUCT` over the capex row with a boolean mask on elapsed months —
straightforward to fill right since the mask shifts consistently with the column.

**Check**: `PP&E Rollforward Check` = 0 for every month.

---

## Phase 5 — Debt schedule

New section on `08_Forecast_BS`, below the PP&E schedule:

```
Opening Debt                  = <prior month Closing Debt>; first bridge month (Jan 2026) = £6,000,000 (mart_opening_balance_sheet.debt_gbp)
Scheduled Repayment           = MIN(Scheduled Monthly Repayment, Opening Debt)
Cash Before Financing (pre-interest)
                              = Opening Cash (from CFS, Phase 8) + Operating Cash Flow BEFORE interest
                                + Investing Cash Flow - Scheduled Repayment
Interest Buffer               = Opening Debt × (Interest Rate / 12)
Required Draw                 = MAX(0, Minimum Cash Threshold + Interest Buffer - Cash Before Financing (pre-interest))
Discretionary Sweep           = IF(Cash Sweep Switch = 1, MAX(0, Cash Before Financing (pre-interest) - Interest Buffer - Minimum Cash Threshold), 0)
                                 capped at MAX(0, Opening Debt - Scheduled Repayment)
Closing Debt                  = Opening Debt - Scheduled Repayment - Discretionary Sweep + Required Draw
Average Debt Balance          = (Opening Debt + Closing Debt) / 2
Interest Expense              = Average Debt Balance × (Interest Rate / 12)
Debt Continuity Check          = Closing Debt - (Opening Debt - Scheduled Repayment - Discretionary Sweep + Required Draw)   [must = 0]
```

### Circularity: resolved algebraically, not by iteration

The classic loop (interest → net income → cash → draw → debt → interest) is broken by a
deliberate convention: **the draw/sweep decision is sized on pre-interest cash, with a
conservative interest buffer estimated on the opening balance**. Interest expense itself is
then computed on the average balance *after* the financing decision — so no formula depends
on its own output, the calculation chain is acyclic, and **iterative calculation is not
required for the model to solve**.

The convention's residual imprecision is tiny and conservative by construction: the buffer
uses the opening balance while true interest uses the average balance, so the draw is
marginally over-sized in draw months (never under-sized — minimum cash cannot be breached by
the approximation). At the assumed rates the discrepancy is bounded by
`(rate/12) × |draw|/2` — single-digit thousands at most.

Keep iterative calculation **available but off** by default (`File → Options → Formulas`),
and keep the Circularity Breaker assumption from Phase 2 as a belt-and-braces recovery tool:
if a future edit ever introduces a true circular chain, Excel will warn rather than silently
converge, which is the correct failure mode. This design must behave identically across all
three scenarios — see the scenario sweep check below.

**Checks**:
- `Debt Continuity Check` = 0 every month, **in all three scenarios** (flip
  `02_Control!$B$14` through Base / Downside / Upside and confirm — the Downside case, with
  its higher rate, larger minimum-cash threshold and weaker cash generation, is the one most
  likely to exercise the draw logic).
- Closing Debt never negative (`Discretionary Sweep` explicitly capped).
- With Cash Sweep Switch = 0 (default), the £6.0m facility amortises at the scheduled pace
  rather than vanishing immediately despite £28m opening cash — the "must not auto-repay just
  because cash is high" requirement.
- Closing cash ≥ Minimum Cash Threshold in every month where a draw occurred.

---

## Phase 6 — Tax schedule

New section, `07_Forecast_IS` (below Profit Before Tax) or `08_Forecast_BS` — either works
since it only needs PBT as an input; recommend keeping it next to the IS for readability:

```
Profit Before Tax             = <from Phase 3>
Opening Tax-Loss Carryforward = <prior month Closing>; first bridge month (Jan 2026) = £0 (assumption, Phase 2)
Taxable Profit Before Relief  = MAX(0, Profit Before Tax)
Tax Losses Utilised           = MIN(Opening Tax-Loss Carryforward, Taxable Profit Before Relief)
Taxable Profit After Relief   = Taxable Profit Before Relief - Tax Losses Utilised
Current Tax Expense           = Taxable Profit After Relief × Tax Rate
Current-Period Loss Generated = MAX(0, -Profit Before Tax)
Closing Tax-Loss Carryforward = Opening Tax-Loss Carryforward - Tax Losses Utilised + Current-Period Loss Generated
Tax Payable (opening)         = <prior month Tax Payable (closing)>
Cash Tax Paid                 = <prior month's Current Tax Expense>   (one-month lag)
Tax Payable (closing)         = Tax Payable (opening) + Current Tax Expense - Cash Tax Paid
Tax Rollforward Check         = Closing Tax-Loss Carryforward - (Opening - Utilised + Generated)   [must = 0]
```

`Current Tax Expense` feeds `Net Income` (Phase 3). `Tax Payable (closing)` feeds the balance
sheet (Phase 7). `Cash Tax Paid` feeds the cash flow statement (Phase 8).

Given the Base-case glide path only reaches positive PBT around month 29 (see Phase 9), the
tax-loss carryforward will have accumulated substantially by then and should fully shelter
taxable profit for several months after breakeven — a believable "no cash tax for years after
a loss-making stretch" pattern the schedule should show explicitly, not something to
special-case.

**Check**: `Tax Rollforward Check` = 0 every month; `Current Tax Expense` is £0 for every month
while `Opening Tax-Loss Carryforward` still exceeds `Taxable Profit Before Relief`.

---

## Phase 6a — H1 2026 modelled-actual bridge (model-critical)

The opening balance sheet anchors at **31 Dec 2025**; actuals run to **30 Jun 2026**. The
balance sheet and CFS therefore start six months *before* the forecast does, in a clearly
labelled `Modelled Actual (bridge)` regime. Run Phases 4–8's schedule mechanics over
Jan–Jun 2026 with this line-by-line basis:

| Line | H1 2026 treatment | Basis |
| --- | --- | --- |
| Revenue, opex, operating profit | **Actual** (from the Phase 1 feed) | Actual |
| AR, AP, Deferred Revenue balances | **Actual** month-end balances (feed) | Actual |
| Cash collected / supplier paid / payroll paid | **Actual** (feed) | Actual |
| Capex | Capex % of Revenue × **actual** revenue | Modelled |
| Depreciation | Phase 4 mechanics from the Dec 2025 opening base | Modelled |
| Debt, interest | Phase 5 mechanics (scheduled repayments only — with £28m opening cash the minimum-cash draw will not trigger) | Modelled |
| Tax | Phase 6 mechanics — H1 2026 PBT is negative throughout, so tax expense is £0 and losses accrue to the carryforward | Modelled |
| Retained earnings | Rolls forward from Dec 2025 with bridge Net Income | Derived |
| Cash | Computed from the CFS, as everywhere else — never plugged | Derived |

Because revenue, working capital and operating cash movements are *actual* and only
capex/depreciation/debt/tax are modelled (all small and assumption-explicit in H1 2026), the
30 Jun 2026 closing balance sheet this produces is a defensible cutover anchor — and it is
**derived, disclosed and checkable**, not asserted. The balance check (Phase 7) must hold
through the bridge months exactly as it does in forecast months.

One acknowledged imperfection to disclose in `01_Model_Map` rather than hide: bridge-period
cash movements combine the feed's actual collections/payments with modelled interest/capex/
tax cash flows, so bridge closing cash is "actuals-led modelled", not statutory. If the
warehouse later gains a true 30 Jun 2026 statutory anchor (a second `mart_opening_balance_sheet`
row), swap the forecast opening to that and demote the bridge to a reconciliation exhibit —
the structure anticipates this.

**Check**: balance check = 0 for all six bridge months; bridge closing cash ≥ 0 and moves
plausibly from £28.0m (H1 2026 operating burn is roughly £1.5–2.5m/month on actuals, so
expect roughly £13–19m at Jun 2026 before modelled capex/debt effects).

---

## Phase 7 — Real balance sheet (`08_Forecast_BS` rebuild)

Below the PP&E and debt schedules, rebuild the summary section:

```
Assets
  Cash                         = <closing cash from CFS, Phase 8>
  Accounts Receivable          = <existing row, unchanged mechanism>
  Prepaids & Other Current     = <first bridge month (Jan 2026) = £1,250,000 (mart_opening_balance_sheet.prepaids_other_current_assets_gbp), held flat or grown with revenue — flat is fine, it's immaterial>
  Net PP&E                     = <Phase 4 Closing Net PP&E>
  Total Assets                 = SUM of the above

Liabilities
  Accounts Payable             = <existing row, unchanged>
  Deferred Revenue             = <existing row, unchanged>
  Debt                         = <Phase 5 Closing Debt>
  Tax Payable                  = <Phase 6 Tax Payable (closing)>
  Total Liabilities            = SUM of the above

Equity
  Share Capital                = <prior month, constant>; first bridge month (Jan 2026) = £5,000,000 (mart_opening_balance_sheet.share_capital_gbp)
  Retained Earnings            = <prior month Retained Earnings> + <Phase 3 Net Income, this month>; first bridge month (Jan 2026) base = £5,172,593.20 (mart_opening_balance_sheet.retained_earnings_gbp)
  Total Equity                 = Share Capital + Retained Earnings

Balance Check                 = Total Assets - (Total Liabilities + Total Equity)   [must = 0 every month from Jan 2026]
```

**Pre-anchor columns (Jan 2023 – Dec 2025): every balance-sheet line renders "n/a" (blank),
never zero, and the Balance Check row reads "n/a"** — use the period-regime header in row 5
to drive this (`=IF(X$6, <calculation>, "n/a")` off the `is_integrated_model_period` flag —
see the mechanical regime enforcement section). A zero would claim a balance
sheet exists and balances; a blank says truthfully that none exists before the anchor.

Add the retained-earnings basis note row directly beneath Retained Earnings (see consequence
2 in the period-regime section): anchor equity is statutory, pre-anchor P&L is an operational
proxy, bases deliberately unreconciled.

This is the headline new check the old workbook never had. It will only hold if Phases 3-8 are
internally consistent — treat any nonzero Balance Check as a signal to recheck the schedule
that changed most recently, not something to plug around.

---

## Phase 8 — Real cash flow statement (`09_Forecast_CFS` rebuild)

```
Operating Activities
  Net Income                   = <Phase 3>
  + Depreciation & Amortisation = <Phase 4 Total Depreciation>
  - Increase in AR              = -(AR this month - AR prior month)
  + Increase in Deferred Revenue = (Deferred Revenue this month - prior month)
  + Increase in AP               = (AP this month - prior month)
  Cash Tax Paid                  = -<Phase 6 Cash Tax Paid>
  Net Cash from Operations       = SUM of the above

Investing Activities
  Capex                         = -<Phase 4 Capex>
  Net Cash from Investing       = Capex

Financing Activities
  Debt Draws                    = <Phase 5 Required Draw>
  Scheduled Repayment           = -<Phase 5 Scheduled Repayment>
  Discretionary Sweep           = -<Phase 5 Discretionary Sweep>
  Net Cash from Financing       = SUM of the above

Memo: Operating CF before Interest = Net Cash from Operations + Interest Expense
                                  (feeds the debt schedule's pre-interest draw sizing, Phase 5)

Net Change in Cash              = Net Cash from Operations + Net Cash from Investing + Net Cash from Financing
Opening Cash                    = <prior month Closing Cash>; first bridge month (Jan 2026) = £28,000,000 (mart_opening_balance_sheet.cash_gbp)
Closing Cash                    = Opening Cash + Net Change in Cash
Cash Reconciliation Check       = Closing Cash - <Phase 7 Balance Sheet Cash>   [must = 0]
```

Working-capital deltas use the same sign convention real statutory CFS statements use (an
increase in a current asset is a cash outflow; an increase in a current liability is a cash
inflow) — this is the one place a sign error silently breaks the balance check three sheets
away, so double check each delta's direction against a single month by hand before filling
right.

**Pre-anchor columns (Jan 2023 – Dec 2025): the CFS does not exist — render "n/a" for every
line**, same header-driven pattern as the balance sheet. The statement begins Jan 2026, where
Opening Cash = the £28.0m anchor. (The old workbook's "cash bridge" ran from Jan 2023 off an
assumed £10m opening cash — that series was never anchored to anything and is retired
entirely; do not carry it forward.)

**Check**: `Cash Reconciliation Check` = 0 every month from Jan 2026 — this is what makes
Phase 7's `Cash` line legitimate (computed here, never a plug).

---

## Phase 9 — DCF fix (`10_DCF`)

No structural changes to the DCF engine (WACC, mid-year discounting, terminal value, sensitivity
table, and checks are all already sound) — it re-points at the now-credible IS from Phase 3.

### Calibration bridge (the arithmetic behind the breakeven claim, derived not reverse-engineered)

| Metric | Historical basis (trailing 12m, presented) | Forecast assumption (Base) | Result |
|---|---|---|---|
| Starting revenue (Jun 2026) | £5,797,388/mo | — | £5.80m/mo |
| Monthly revenue growth | ~+0.28%/mo actual | **+0.60%/mo** (modest reacceleration) | £7.45m/mo at Dec 2029 |
| Starting opex (Jun 2026, presented) | £7,733,565/mo | — | £7.73m/mo |
| Monthly opex growth (blended) | ~−0.35%/mo actual | **−0.39%/mo** (payroll −0.4% × ~94% weight + AP −0.2% × ~6% weight) | £6.56m/mo at Dec 2029 |
| Operating margin | −33.4% at Jun 2026 | derived from the two rates above | **+11.9%** at Dec 2029 |
| Breakeven month | — | derived | **month 29 ≈ Dec 2028** |

Breakeven derivation, explicitly: revenue and opex converge when
`(1.006)^t / (0.9961)^t = opex₀/rev₀ = 1.334`, i.e.
`t = ln(1.334) / (ln 1.006 − ln 0.9961) = 0.2882 / 0.00989 ≈ 29.1 months` after Jul 2026 →
**December 2028**. (Note: applying the *trailing* rates of +0.3%/−0.35% instead gives
`0.2882 / 0.0065 ≈ 44 months` — the forecast reaches breakeven sooner than pure trend
extrapolation precisely because the Base case assumes reacceleration to +0.6%. That gap
between trend and assumption is the deliberate, visible judgment call of the Base case, and
the Downside case (+0.2% growth) intentionally does *not* reach breakeven in the horizon.)

The "Target Operating Margin" assumption is a **guardrail, not a driver**: opex growth is the
mechanical input, and if the derived margin at Dec 2029 deviates materially from the target,
the assumption pair should be revisited — flag this relationship in a note cell next to the
assumption rather than force-fitting.

Month-by-month path produced by these two rates:

| Month (from Jul 2026) | Revenue/mo | Opex/mo | Operating Margin |
|---|---|---|---|
| 0 (start) | £5.80m | £7.73m | −33.4% |
| 12 | £6.23m | £7.38m | −18.5% |
| 24 | £6.69m | £7.04m | −5.2% |
| **29 (breakeven)** | £6.90m | £6.91m | **~0%** |
| 36 | £7.19m | £6.72m | +6.6% |
| 42 (Dec 2029, end of horizon) | £7.45m | £6.56m | **+11.9%** |

### UFCF construction — explicit conventions

- **Unlevered**: UFCF = EBIT − unlevered taxes + D&A − Capex − ΔNWC. **Interest expense is
  excluded from UFCF entirely** — it affects the levered statements (Phase 3/5) but never the
  DCF cash flows.
- **Unlevered taxes**: tax rate × max(0, EBIT), with the same loss-carryforward sheltering
  logic as Phase 6 but computed on EBIT (not PBT) so the tax shield in the DCF is consistent
  and unlevered. Keep this as a separate small row block on `10_DCF` — do not reuse the
  levered tax numbers from Phase 6.
- **Net debt appears exactly once**: in the EV → equity bridge on `12_Outputs`
  (Equity Value = EV − closing net debt). Never inside UFCF.
- **Terminal value uses a stabilised year**: annualise the final forecast year's UFCF only if
  margin has stabilised by then; at +11.9% and still glancing upward, apply the terminal
  margin implied by the Target Operating Margin assumption (12% Base) to terminal-year revenue
  rather than annualising a still-improving December run-rate.
- **Disclose TV % of EV** on the DCF sheet (a single cell: PV of terminal value / EV). For a
  business only just profitable at horizon end this will be high (likely 80%+) — that is
  expected, but it must be visible, not discovered.
- **Commercial coherence outputs**: EV / latest headline ARR and EV / terminal-year revenue,
  shown beside the sensitivity table. Sanity band: a ~6% grower at ~12% operating margin
  should land well below the 5–10× ARR multiples of high-growth SaaS — think low single-digit
  ARR multiple. If the result is outside 0.5×–3× ARR, interrogate the assumptions before
  accepting it.

Re-run the DCF and confirm:

- `FCF Sign Check` no longer reads "All forecast FCF negative" (early forecast years will
  still show negative FCF pre-breakeven; that's correct and expected — check that later years
  turn positive).
- `Terminal Growth < WACC Check` still reads OK (unchanged: 2.5% < 10%).
- Enterprise Value is **positive** and of a sensible order of magnitude (a company reaching
  ~£90m annualised revenue at 12% margin, WACC 10%, terminal growth 2.5% should land in the
  tens of millions, not hundreds — if the result is wildly larger, recheck the reinvestment
  assumption isn't now understating true capex needs, since `Capex % of Revenue` from Phase 2
  should probably replace the old flat "Reinvestment % of Revenue" DCF-only assumption rather
  than stacking both).

**Action**: retire the old `Reinvestment % of Revenue` DCF assumption and reinvestment line —
Unlevered FCF should now subtract actual `Capex` (Phase 4) directly, since a real capex
schedule now exists and a second, separate reinvestment plug would double-count.

---

## Phase 10 — Outputs contract (`12_Outputs`)

Populate with one column per scenario (Base / Downside / Upside — re-run the whole workbook
under `02_Control!$B$14` set to each scenario in turn, or better, build formulas that pull the
scenario-specific assumption column directly so all three compute simultaneously):

```
                                Base        Downside    Upside
Enterprise Value                <10_DCF!EV>  ...         ...
Net Debt (closing, Dec 2029)    <Phase 5 Closing Debt> - <Phase 7 Cash>
Equity Value                    Enterprise Value - Net Debt
Latest Headline ARR             <Phase 1 feed, latest month>
Implied ARR Multiple            Enterprise Value / Latest Headline ARR
Revenue (Dec 2029, annualised)  <Phase 3, latest month x 12>
Operating Margin (Dec 2029)     <Phase 3, latest month>
Net Income (Dec 2029, annualised)
Closing Cash (Dec 2029)         <Phase 8>
Closing Debt (Dec 2029)         <Phase 5>
Balance Check (max abs, all months)   <Phase 7 — should read as "0" i.e. a clean bill of health>
```

That display table is for humans. **Below it, build the machine-readable contract block** —
a flat table (one row per scenario × metric) that the extraction pipeline and the portal
consume. Stable `metric_code` values are the contract; display labels above can change freely
without breaking anything downstream.

```
model_version | output_schema_version | data_as_of_date | actuals_cutoff_date | forecast_start_date | scenario_code | metric_code | reporting_period | metric_value | unit | model_readiness_status | balance_check_status
v0.3          | 1                     | <anchor_date +1d>| <actuals_cutoff>    | <forecast_start>    | BASE          | enterprise_value        | 2029-12 | ... | GBP   | <from feed summary> | <PASS if max abs balance check = 0>
v0.3          | 1                     | ...             | ...                 | ...                 | BASE          | equity_value            | 2029-12 | ... | GBP   | ...                 | ...
```

Fixed `metric_code` vocabulary (version 1 of the output schema — additions are allowed,
renames are a schema-version bump):

| metric_code | unit | Source |
|---|---|---|
| `enterprise_value` | GBP | 10_DCF |
| `equity_value` | GBP | EV − closing net debt |
| `net_debt_closing` | GBP | Phase 5 debt − Phase 8 cash, Dec 2029 |
| `implied_arr_multiple` | ratio | EV / latest headline ARR |
| `ev_to_terminal_revenue` | ratio | EV / terminal-year revenue |
| `revenue_annualised_horizon` | GBP | Phase 3, Dec 2029 × 12 |
| `operating_margin_horizon` | ratio | Phase 3, Dec 2029 |
| `net_income_annualised_horizon` | GBP | Phase 3, Dec 2029 × 12 |
| `closing_cash_horizon` | GBP | Phase 8, Dec 2029 |
| `closing_debt_horizon` | GBP | Phase 5, Dec 2029 |
| `breakeven_month` | date | first month operating profit ≥ 0 |
| `terminal_value_pct_of_ev` | ratio | 10_DCF disclosure cell |
| `max_abs_balance_check` | GBP | Phase 7, max across all months (0 = clean) |

`scenario_code` values: `BASE` / `DOWNSIDE` / `UPSIDE` (stable, uppercase — matching the
`02_Control` scenario list but code-cased for machine consumption).

This is the exact shape the portal's Forecast & Valuation page is already waiting for (its
"Outputs contract: planned" step). Extracting this sheet into a portal-consumable artifact
(scenario selector + DCF cards) is a separate, follow-on piece of work — not part of this
build.

---

## Appendix — Phase 1 parallel-run reconciliation (old vs new feed)

Before the old Power Query layer is deleted, the new feed was reconciled against the v0.21
workbook's cached table for **all 42 months × all 29 consumed columns** (1,218 checks —
numeric to a 0.0001% / £0.01 tolerance, statuses by exact string match). Result:
**1,217 of 1,218 pass.** Full detail: `analysis/exports/feed_reconciliation_v021_vs_v03.csv`
(old value, new value, variance, variance %, pass/fail per month per column).

The single intentional difference, documented per policy:

| Month | Column | Old | New | Why the new value is correct |
|---|---|---|---|---|
| Dec 2023 | `deferred_revenue_model_status` | `OK` | `Check` | The governed deferred-revenue rollforward control (`mart_model_readiness_controls`, Model Blocking) flags an exception in Dec 2023 that the old Excel-side variance formula missed. The warehouse control supersedes the ad hoc check — this month was already shown as Blocked in the portal's readiness views. |

Reconciliation also drove four deliberate semantic recoveries (initial drafts of the new feed
had subtly different definitions; all were corrected to match the old values exactly rather
than documented away): the billing basis (revenue-waterfall/deferred additions, not O2C
invoiced), operating profit on the recognised-revenue basis even in GL-closed months, revenue
per FTE on recognised revenue, and both ARR memo columns (`headline − (beginning + net delta)`
and `ending MRR − headline/12` respectively).

---

## Full build-order checklist

- [ ] Phase 1: actuals feed migrated, `11_Audit_Checks` unchanged and passing
- [ ] Regime machinery: `anchor_date`/`actuals_cutoff`/`forecast_start` named cells in `02_Control`; period_regime + is_integrated_model_period + is_forecast_period flag rows on every monthly sheet, formula-driven from the named cells
- [ ] Phase 2: assumptions added/recalibrated; iterative calculation left OFF (circularity solved algebraically, Phase 5)
- [ ] Phase 3: IS extended to Net Income, historical months unaffected
- [ ] Phase 4: PP&E schedule, rollforward check = 0
- [ ] Phase 5: debt schedule, continuity check = 0 **in all three scenarios**, facility doesn't vanish on day one, no iterative calculation required
- [ ] Phase 6: tax schedule, rollforward check = 0, no tax while losses shelter profit
- [ ] Phase 6a: H1 2026 bridge — balance check holds Jan–Jun 2026, bridge cash lands plausibly from the £28m anchor
- [ ] Phase 7: balance sheet, **balance check = 0 every month from Jan 2026**; pre-anchor columns read "n/a", not zero; retained-earnings basis note present
- [ ] Phase 8: CFS begins Jan 2026 from the £28m anchor; pre-anchor columns "n/a"; old £10m unanchored cash bridge retired
- [ ] Phase 8: cash flow statement, cash reconciliation check = 0 every month
- [ ] Phase 9: DCF re-run, EV positive and plausible, FCF sign check reads correctly
- [ ] Phase 10: outputs contract populated for all three scenarios
- [ ] Save as `atlas_integrated_financial_model_v0.3.xlsx`
