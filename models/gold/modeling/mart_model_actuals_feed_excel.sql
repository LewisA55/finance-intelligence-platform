{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'mart', 'modelling', 'excel_feed', 'three_statement_model']
) }}

/*
    Excel-ready actuals feed: a thin, purpose-built wrapper over
    mart_model_actuals_feed that replaces the workbook's own 16-query Power
    Query layer (7 raw domain imports + 7 monthly rollups + 1 join, each
    reinventing joins and ad hoc control checks Excel had no way to govern).

    Column names are aliased to match the workbook's existing
    tbl_model_feed_final table exactly, so every downstream structured
    reference (`tbl_model_feed_final[column_name]`) keeps working unchanged
    when this feed replaces the Power Query source. Only 29 of the old
    table's 60 columns were ever referenced by a formula anywhere in the
    workbook (verified by grepping every worksheet) - this feed carries only
    those 29, plus reporting_month_date.

    Two categories of column need real logic, not a straight rename:

    1. actual_operating_expense_gbp / actual_operating_profit_gbp /
       actual_operating_margin - the workbook's own Power Query invented a
       payroll+AP proxy here because mart_model_actuals_feed.opex_gbp is
       genuinely 0 outside the 3 GL-closed months. That proxy is now the
       governed, tested, disclosed `operational_opex_proxy` policy (see
       presentation_policy seed / mart_cfo_presented_operating_metrics) -
       reapplied here directly so this feed doesn't need a second
       long-format table join.

    2. The 7 old *_status columns were bespoke per-domain checks. 6 map
       exactly to named controls in mart_model_readiness_controls (matched
       against data/raw/governance/model_readiness_controls.csv): a status
       fires when that control's name appears in the feed's own
       model_blocking_control_names / accepted_limitation_control_names
       lists. The 7th, revenue_vs_o2c_billings_status, isn't a control at
       all - it's the same "commercial ARR isn't reconciled to accounting
       revenue" structural gap the portal's Revenue Quality page discloses,
       computed here directly as a magnitude check, not a governance flag.
*/

with feed as (

    select *
    from {{ ref('mart_model_actuals_feed') }}
    where reporting_scope = 'Company Total'
      and scenario_code = 'ACTUALS'
      and is_actual_period
      -- Matches the workbook's own historical scope exactly (verified:
      -- 42 months, Jan 2023-Jun 2026, per 11_Audit_Checks' own "Expected
      -- 42 / Actual 42" span check). is_actual_period alone reaches back
      -- to Jan 2018 (SaaS-only history) which the workbook never included.
      and has_revenue_actuals
      and has_o2c_actuals

),

-- The workbook's ARR monthly run-rate source is ending MRR from the SaaS
-- movement mart (verified to the penny against the v0.21 cached table) -
-- a column the base feed does not carry, so it is joined here directly.
saas_run_rate as (

    select
        reporting_month_date,
        sum(ending_mrr_gbp) as ending_mrr_gbp
    from {{ ref('mart_saas_arr_movement') }}
    group by 1

),

final as (

    select
        feed.reporting_month_date,

        -- The workbook's billing basis is the revenue-waterfall / deferred
        -- additions series (billings that enter deferred revenue), NOT O2C
        -- invoiced billings — verified against the v0.21 cached table where
        -- billings_gbp equals new_billings_deferred_revenue_gbp in every
        -- month. The gap between the two bases is itself surfaced below as
        -- revenue_vs_o2c_billings_variance_gbp, exactly as the old feed did.
        deferred_revenue_additions_gbp as billings_gbp,
        recognised_revenue_gbp as recognised_revenue_actual_gbp,
        cash_collected_gbp,
        open_ar_gbp as open_ar_exposure_gbp,
        closing_deferred_revenue_gbp,
        ap_spend_gbp as ap_invoice_spend_gbp,
        supplier_cash_paid_gbp,
        open_ap_gbp as open_ap_liability_gbp,
        payroll_cost_gbp,
        active_fte as active_fte_count,
        headline_arr_gbp,
        net_arr_delta_gbp,
        grr as gross_revenue_retention_rate,
        nrr as net_revenue_retention_rate,
        logo_churn as logo_churn_rate,
        -- Old semantics: recognised revenue per FTE, always — never the GL
        -- revenue line (the feed's own revenue_per_fte_gbp switches to GL
        -- revenue for closed months, which the model's IS does not use).
        case
            when active_fte > 0 then recognised_revenue_gbp / active_fte
            else null
        end as revenue_per_active_fte_gbp,

        -- Presented-basis opex/profit/margin: the operational proxy
        -- (payroll + AP spend) ahead of GL close, matching what Excel's
        -- own Power Query already computed, now governed and disclosed.
        -- Profit and margin are always on the recognised-revenue basis (the
        -- IS revenue line the model actually uses) — even for GL-closed
        -- months where a slightly different GL revenue figure exists. Only
        -- the expense side switches to the closed ledger when available.
        case
            when has_financial_actuals then opex_gbp
            else payroll_cost_gbp + ap_spend_gbp
        end as actual_operating_expense_gbp,
        recognised_revenue_gbp - case
            when has_financial_actuals then opex_gbp
            else payroll_cost_gbp + ap_spend_gbp
        end as actual_operating_profit_gbp,
        case
            when recognised_revenue_gbp = 0 then null
            else (
                recognised_revenue_gbp - case
                    when has_financial_actuals then opex_gbp
                    else payroll_cost_gbp + ap_spend_gbp
                end
            ) / recognised_revenue_gbp
        end as actual_operating_margin,

        -- ARR-bridge memo columns: the same reconciliation Excel displayed,
        -- computed from the mart's own bridge components. Informational
        -- only - the SaaS ARR bridge is a known, accepted definitional
        -- limitation (see saas_arr_control_status below), not a forecast
        -- driver.
        -- Old semantics preserved exactly (verified via the 42-month
        -- reconciliation against the v0.21 cached table): bridge variance =
        -- headline ARR minus (beginning ARR + net ARR delta); run-rate
        -- variance = (ending ARR minus headline ARR) / 12, per the audit
        -- sheet's own note that ending_arr is the run-rate source.
        feed.headline_arr_gbp - (feed.beginning_arr_gbp + feed.net_arr_delta_gbp) as arr_bridge_variance_gbp,
        saas_run_rate.ending_mrr_gbp - (feed.headline_arr_gbp / 12) as arr_monthly_run_rate_variance_gbp,

        -- Governed status columns: fire from the same named controls the
        -- Control Tower and Forecast & Valuation pages already read.
        case
            when accepted_limitation_control_names like '%Accounts payable control exceptions%'
                then 'Control Exception'
            else 'OK'
        end as ap_control_status,
        case
            when model_blocking_control_names like '%Deferred revenue rollforward exceptions%'
                then 'Check'
            else 'OK'
        end as deferred_revenue_model_status,
        case
            when accepted_limitation_control_names like '%SaaS ARR bridge control issues%'
                then 'Control Exception'
            else 'OK'
        end as saas_arr_control_status,
        case
            when accepted_limitation_control_names like '%SaaS retention control issues%'
                then 'Control Exception'
            else 'OK'
        end as saas_retention_control_status,
        case
            when accepted_limitation_control_names like '%Workforce HRIS/payroll control issues%'
                then 'Control Exception'
            else 'OK'
        end as workforce_control_status,
        case
            when accepted_limitation_control_names like '%SaaS ARR bridge control issues%'
                then 'Source Definition Difference'
            else 'OK'
        end as arr_bridge_status,

        -- Structural, not governance: the gap between the two billing bases
        -- (revenue-waterfall billings that enter deferred revenue vs O2C
        -- invoiced billings). Deliberately disclosed, not reconciled — they
        -- measure different things by design. Threshold reproduces the old
        -- feed's behaviour exactly: Definition Difference at >= 10% of the
        -- O2C-invoiced base.
        deferred_revenue_additions_gbp - billings_gbp as revenue_vs_o2c_billings_variance_gbp,
        case
            when billings_gbp = 0 then 'OK'
            when abs(deferred_revenue_additions_gbp - billings_gbp) >= 0.10 * abs(billings_gbp)
                then 'Definition Difference'
            when abs(deferred_revenue_additions_gbp - billings_gbp) > 0
                then 'Minor Variance'
            else 'OK'
        end as revenue_vs_o2c_billings_status,

        current_timestamp as _atlas_modelled_at

    from feed
    left join saas_run_rate
        on feed.reporting_month_date = saas_run_rate.reporting_month_date

)

select *
from final
order by reporting_month_date
