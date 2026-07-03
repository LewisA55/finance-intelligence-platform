{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'mart', 'presentation', 'operating_metrics']
) }}

/*
    Presented-basis operating metrics (long format).

    One row per reporting month x metric, carrying both the as-found value
    (raw model-serving feed, audit telemetry included) and the presented
    value the CFO surface should show, with the policy, adjustment and
    disclosure that connect them.

    Policies applied (see the presentation_policy seed):
      - trailing_partial_clip: a final period that collapses versus the prior
        period is a boundary artifact, clipped from presentation.
      - operational_opex_proxy: before GL close, opex reflects operational
        capture; presented with a partial-capture disclosure.
      - timing_lag_disclosure: collection measures lag billings by design.
      - workforce_ghost_disclosure: payroll includes ghost-flagged records,
        an accepted limitation under the readiness policy.
*/

with policy as (

    select *
    from {{ ref('presentation_policy') }}

),

clip_policy as (

    select threshold_ratio
    from policy
    where policy_key = 'trailing_partial_clip'

),

feed as (

    select
        f.*,
        lag(f.headline_arr_gbp) over (order by f.reporting_month_date) as prior_headline_arr_gbp,
        row_number() over (order by f.reporting_month_date desc) as recency_rank
    from {{ ref('mart_model_actuals_feed') }} as f
    where f.reporting_scope = 'Company Total'
      and f.scenario_code = 'ACTUALS'
      and f.model_period_status = 'Actual'

),

flagged as (

    select
        feed.*,
        (
            feed.recency_rank = 1
            and coalesce(feed.prior_headline_arr_gbp, 0) > 0
            and feed.headline_arr_gbp < clip_policy.threshold_ratio * feed.prior_headline_arr_gbp
        ) as saas_trailing_partial_flag
    from feed
    cross join clip_policy

),

metric_rows as (

    select
        reporting_month_date,
        'recognised_revenue' as metric_code,
        'Recognised revenue' as metric_name,
        'GBP' as unit,
        recognised_revenue_gbp as as_found_value,
        recognised_revenue_gbp as presented_value,
        false as excluded_from_presentation_flag,
        'Presented' as presentation_basis_status,
        cast(null as varchar) as disclosure_text,
        'Presented' as control_treatment,
        cast(null as varchar) as policy_key
    from flagged

    union all

    select
        reporting_month_date,
        'billings',
        'Billings',
        'GBP',
        billings_gbp,
        billings_gbp,
        false,
        'Presented',
        null,
        'Presented',
        null
    from flagged

    union all

    select
        reporting_month_date,
        'cash_collected',
        'Cash collected',
        'GBP',
        cash_collected_gbp,
        cash_collected_gbp,
        false,
        'Presented with disclosure',
        (select disclosure_template from policy where policy_key = 'timing_lag_disclosure'),
        'Presented with disclosure',
        'timing_lag_disclosure'
    from flagged

    union all

    select
        reporting_month_date,
        'cash_collection_rate',
        'Cash collection rate',
        'ratio',
        cash_collection_rate,
        cash_collection_rate,
        false,
        'Presented with disclosure',
        (select disclosure_template from policy where policy_key = 'timing_lag_disclosure'),
        'Presented with disclosure',
        'timing_lag_disclosure'
    from flagged

    union all

    select
        reporting_month_date,
        'headline_arr',
        'Headline ARR',
        'GBP',
        headline_arr_gbp,
        case when saas_trailing_partial_flag then null else headline_arr_gbp end,
        saas_trailing_partial_flag,
        case
            when saas_trailing_partial_flag then 'Clipped - partial period'
            else 'Presented'
        end,
        case
            when saas_trailing_partial_flag
                then (select disclosure_template from policy where policy_key = 'trailing_partial_clip')
            else null
        end,
        case when saas_trailing_partial_flag then 'Clipped from presentation' else 'Presented' end,
        case when saas_trailing_partial_flag then 'trailing_partial_clip' else null end
    from flagged

    union all

    select
        reporting_month_date,
        'nrr',
        'Net revenue retention',
        'ratio',
        nrr,
        case when saas_trailing_partial_flag then null else nrr end,
        saas_trailing_partial_flag,
        case
            when saas_trailing_partial_flag then 'Clipped - partial period'
            else 'Presented'
        end,
        case
            when saas_trailing_partial_flag
                then (select disclosure_template from policy where policy_key = 'trailing_partial_clip')
            else null
        end,
        case when saas_trailing_partial_flag then 'Clipped from presentation' else 'Presented' end,
        case when saas_trailing_partial_flag then 'trailing_partial_clip' else null end
    from flagged

    union all

    -- GL opex only exists for closed periods; ahead of close the presented
    -- basis substitutes the operational proxy (payroll + AP spend) — the same
    -- basis the Excel workbook models — and discloses the substitution.
    select
        reporting_month_date,
        'opex',
        'Operating expenses',
        'GBP',
        opex_gbp,
        case
            when has_financial_actuals then opex_gbp
            else payroll_cost_gbp + ap_spend_gbp
        end,
        false,
        case
            when has_financial_actuals then 'Presented'
            else 'Presented - operational proxy'
        end,
        case
            when has_financial_actuals then null
            else (select disclosure_template from policy where policy_key = 'operational_opex_proxy')
        end,
        case when has_financial_actuals then 'Presented' else 'Presented with disclosure' end,
        case when has_financial_actuals then null else 'operational_opex_proxy' end
    from flagged

    union all

    select
        reporting_month_date,
        'operating_profit',
        'Operating profit',
        'GBP',
        operating_profit_gbp,
        case
            when has_financial_actuals then operating_profit_gbp
            else recognised_revenue_gbp - (payroll_cost_gbp + ap_spend_gbp)
        end,
        false,
        case
            when has_financial_actuals then 'Presented'
            else 'Presented - operational proxy'
        end,
        case
            when has_financial_actuals then null
            else (select disclosure_template from policy where policy_key = 'operational_opex_proxy')
        end,
        case when has_financial_actuals then 'Presented' else 'Presented with disclosure' end,
        case when has_financial_actuals then null else 'operational_opex_proxy' end
    from flagged

    union all

    select
        reporting_month_date,
        'payroll_cost',
        'Payroll cost',
        'GBP',
        payroll_cost_gbp,
        payroll_cost_gbp,
        false,
        'Presented with disclosure',
        (select disclosure_template from policy where policy_key = 'workforce_ghost_disclosure'),
        'Presented with disclosure',
        'workforce_ghost_disclosure'
    from flagged

    union all

    select
        reporting_month_date,
        'active_fte',
        'Active FTE',
        'count',
        active_fte,
        active_fte,
        false,
        'Presented with disclosure',
        (select disclosure_template from policy where policy_key = 'workforce_ghost_disclosure'),
        'Presented with disclosure',
        'workforce_ghost_disclosure'
    from flagged

),

final as (

    select
        md5(strftime(reporting_month_date, '%Y-%m-%d') || '|' || metric_code) as presented_metric_hk,
        reporting_month_date,
        metric_code,
        metric_name,
        unit,
        as_found_value,
        presented_value,
        as_found_value - coalesce(presented_value, 0) as adjustment_amount,
        excluded_from_presentation_flag,
        presentation_basis_status,
        disclosure_text,
        control_treatment,
        policy_key,
        current_timestamp as _atlas_modelled_at
    from metric_rows

)

select *
from final
