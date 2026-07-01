{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'mart', 'modelling', 'model_serving', 'three_statement_model', 'cfo']
) }}

with month_spine as (

    select distinct posting_period as reporting_month_date
    from {{ ref('mart_financial_performance') }}
    where posting_period is not null

    union

    select distinct invoice_month as reporting_month_date
    from {{ ref('mart_o2c_customer_collections') }}
    where invoice_month is not null

    union

    select distinct cast(reporting_month as date) as reporting_month_date
    from {{ ref('mart_revenue_waterfall') }}
    where reporting_month is not null

    union

    select distinct period_month as reporting_month_date
    from {{ ref('mart_deferred_revenue_control') }}
    where period_month is not null

    union

    select distinct reporting_month_date
    from {{ ref('mart_ap_working_capital_control') }}
    where reporting_month_date is not null

    union

    select distinct reporting_month_date
    from {{ ref('mart_workforce_cost_control') }}
    where reporting_month_date is not null

    union

    select distinct reporting_month_date
    from {{ ref('mart_saas_arr_movement') }}
    where reporting_month_date is not null

),

financial as (

    select
        posting_period as reporting_month_date,
        sum(case when account_class = 'Revenue' then actual_amount_gbp else 0 end) as actual_revenue_gbp,
        sum(case when account_class = 'Expense' then actual_amount_gbp else 0 end) as opex_gbp,
        sum(case when account_class = 'Revenue' then budget_amount_gbp else 0 end) as budget_revenue_gbp,
        sum(case when account_class = 'Expense' then budget_amount_gbp else 0 end) as budget_opex_gbp,
        sum(case when account_class = 'Revenue' then forecast_amount_gbp else 0 end) as forecast_revenue_gbp,
        sum(case when account_class = 'Expense' then forecast_amount_gbp else 0 end) as forecast_opex_gbp,
        sum(case when is_defect then 1 else 0 end) as financial_defect_row_count
    from {{ ref('mart_financial_performance') }}
    where forecast_version_code = 'FC_BASE_CASE'
    group by 1

),

o2c as (

    select
        invoice_month as reporting_month_date,
        sum(billed_amount_gbp) as billings_gbp,
        sum(allocated_amount_gbp) as cash_collected_gbp,
        sum(open_invoice_exposure_gbp) as open_ar_gbp,
        sum(over_applied_allocation_amount_gbp) as over_applied_cash_gbp,
        sum(defective_invoice_count) as defective_invoice_count,
        sum(case when has_over_applied_cash then 1 else 0 end) as over_applied_cash_customer_month_count
    from {{ ref('mart_o2c_customer_collections') }}
    group by 1

),

revenue as (

    select
        cast(reporting_month as date) as reporting_month_date,
        sum(billed_amount_gbp) as revenue_waterfall_billings_gbp,
        sum(recognised_revenue_actual_gbp) as recognised_revenue_gbp,
        sum(recognised_revenue_scheduled_gbp) as scheduled_recognition_gbp,
        sum(recognised_revenue_total_gbp) as total_recognition_gbp,
        sum(unscheduled_billing_leakage_gbp) as unscheduled_billing_leakage_gbp,
        sum(recognition_variance_gbp) as recognition_variance_gbp,
        sum(case when has_revenue_governance_exception then 1 else 0 end) as revenue_governance_exception_count
    from {{ ref('mart_revenue_waterfall') }}
    group by 1

),

deferred as (

    select
        period_month as reporting_month_date,
        max(period_status) as deferred_period_status,
        sum(corporate_opening_deferred_revenue_gbp) as opening_deferred_revenue_gbp,
        sum(corporate_new_billings_deferred_gbp) as deferred_revenue_additions_gbp,
        sum(corporate_recognised_revenue_gbp) as deferred_revenue_release_gbp,
        sum(corporate_closing_deferred_revenue_gbp) as closing_deferred_revenue_gbp,
        sum(case when has_deferred_revenue_control_exception then 1 else 0 end) as deferred_revenue_control_exception_count
    from {{ ref('mart_deferred_revenue_control') }}
    group by 1

),

ap as (

    select
        reporting_month_date,
        sum(monthly_invoice_total_gbp) as ap_spend_gbp,
        sum(monthly_payment_amount_gbp) as supplier_cash_paid_gbp,
        sum(open_payable_liability_gbp) as open_ap_gbp,
        sum(overdue_payable_liability_gbp) as overdue_ap_gbp,
        sum(case when has_ap_control_exception then 1 else 0 end) as ap_control_exception_count
    from {{ ref('mart_ap_working_capital_control') }}
    group by 1

),

workforce as (

    select
        reporting_month_date,
        sum(payroll_cost_gbp) as payroll_cost_gbp,
        sum(active_fte_count) as active_fte,
        sum(active_headcount_count) as active_headcount_count,
        sum(open_position_count) as open_position_count,
        sum(open_position_monthly_salary_exposure_gbp) as open_position_monthly_salary_exposure_gbp,
        sum(case when has_workforce_control_issue then 1 else 0 end) as workforce_control_issue_count
    from {{ ref('mart_workforce_cost_control') }}
    group by 1

),

saas as (

    select
        reporting_month_date,
        sum(active_arr_gbp) as headline_arr_gbp,
        sum(active_mrr_gbp) as active_mrr_gbp,
        sum(beginning_arr_gbp) as beginning_arr_gbp,
        sum(new_business_arr_gbp) as new_business_arr_gbp,
        sum(expansion_arr_gbp) as expansion_arr_gbp,
        sum(price_increase_arr_gbp) as price_increase_arr_gbp,
        sum(contraction_arr_gbp) as contraction_arr_gbp,
        sum(churn_arr_gbp) as churn_arr_gbp,
        sum(pause_arr_gbp) as pause_arr_gbp,
        sum(net_arr_delta_gbp) as net_arr_delta_gbp,
        sum(ending_arr_gbp) as ending_arr_gbp,
        sum(case when has_saas_control_issue then 1 else 0 end) as saas_arr_control_issue_count
    from {{ ref('mart_saas_arr_movement') }}
    group by 1

),

retention as (

    select
        reporting_month_date,
        sum(beginning_arr_gbp) as retention_beginning_arr_gbp,
        sum(gross_retained_arr_gbp) as gross_retained_arr_gbp,
        sum(net_retained_arr_gbp) as net_retained_arr_gbp,
        sum(beginning_active_customer_count) as beginning_active_customer_count,
        sum(retained_customer_count) as retained_customer_count,
        sum(churned_customer_count) as churned_customer_count,
        sum(case when has_saas_retention_control_issue then 1 else 0 end) as saas_retention_control_issue_count
    from {{ ref('mart_saas_retention') }}
    group by 1

),

control_observations as (

    select reporting_month_date, 'financial_performance_defects' as control_key, financial_defect_row_count as exception_count from financial
    union all select reporting_month_date, 'o2c_collection_defects', defective_invoice_count from o2c
    union all select reporting_month_date, 'o2c_over_applied_cash', over_applied_cash_customer_month_count from o2c
    union all select reporting_month_date, 'revenue_governance_exceptions', revenue_governance_exception_count from revenue
    union all select reporting_month_date, 'deferred_revenue_control_exceptions', deferred_revenue_control_exception_count from deferred
    union all select reporting_month_date, 'ap_control_exceptions', ap_control_exception_count from ap
    union all select reporting_month_date, 'workforce_control_issues', workforce_control_issue_count from workforce
    union all select reporting_month_date, 'saas_arr_control_issues', saas_arr_control_issue_count from saas
    union all select reporting_month_date, 'saas_retention_control_issues', saas_retention_control_issue_count from retention

),

control_rollup as (

    select
        control_observations.reporting_month_date,
        sum(coalesce(control_observations.exception_count, 0)) as total_control_exception_count,
        sum(
            case
                when readiness.model_blocking_flag
                then coalesce(control_observations.exception_count, 0)
                else 0
            end
        ) as model_blocking_exception_count,
        sum(
            case
                when readiness.accepted_limitation_flag
                then coalesce(control_observations.exception_count, 0)
                else 0
            end
        ) as accepted_limitation_exception_count,
        sum(
            case
                when not coalesce(readiness.model_blocking_flag, false)
                 and not coalesce(readiness.accepted_limitation_flag, false)
                then coalesce(control_observations.exception_count, 0)
                else 0
            end
        ) as review_exception_count,
        string_agg(distinct readiness.control_name, '; ' order by readiness.control_name) filter (
            where coalesce(control_observations.exception_count, 0) > 0
              and readiness.model_blocking_flag
        ) as model_blocking_control_names,
        string_agg(distinct readiness.control_name, '; ' order by readiness.control_name) filter (
            where coalesce(control_observations.exception_count, 0) > 0
              and readiness.accepted_limitation_flag
        ) as accepted_limitation_control_names,
        string_agg(distinct readiness.control_name, '; ' order by readiness.control_name) filter (
            where coalesce(control_observations.exception_count, 0) > 0
              and not coalesce(readiness.model_blocking_flag, false)
              and not coalesce(readiness.accepted_limitation_flag, false)
        ) as review_control_names
    from control_observations
    left join {{ ref('mart_model_readiness_controls') }} as readiness
        on control_observations.control_key = readiness.control_key
    group by 1

),

final as (

    select
        md5(strftime(month_spine.reporting_month_date, '%Y-%m-%d') || '|Company Total|ACTUALS') as model_actuals_feed_hk,
        date_dim.date_hk as reporting_month_date_hk,
        month_spine.reporting_month_date,
        'Company Total' as reporting_scope,
        'ACTUALS' as scenario_code,
        'Historical Actuals / Source Scheduled' as scenario_name,
        case
            when coalesce(deferred.deferred_period_status, '') = 'Scheduled'
              or month_spine.reporting_month_date > date '2026-06-01'
                then 'Scheduled'
            else 'Actual'
        end as model_period_status,
        not (
            coalesce(deferred.deferred_period_status, '') = 'Scheduled'
            or month_spine.reporting_month_date > date '2026-06-01'
        ) as is_actual_period,
        (
            coalesce(deferred.deferred_period_status, '') = 'Scheduled'
            or month_spine.reporting_month_date > date '2026-06-01'
        ) as is_scheduled_period,

        coalesce(revenue.recognised_revenue_gbp, 0) as recognised_revenue_gbp,
        coalesce(o2c.billings_gbp, revenue.revenue_waterfall_billings_gbp, 0) as billings_gbp,
        coalesce(o2c.cash_collected_gbp, 0) as cash_collected_gbp,

        coalesce(deferred.opening_deferred_revenue_gbp, 0) as opening_deferred_revenue_gbp,
        coalesce(deferred.deferred_revenue_additions_gbp, 0) as deferred_revenue_additions_gbp,
        coalesce(deferred.deferred_revenue_release_gbp, 0) as deferred_revenue_release_gbp,
        coalesce(deferred.closing_deferred_revenue_gbp, 0) as closing_deferred_revenue_gbp,

        coalesce(o2c.open_ar_gbp, 0) as open_ar_gbp,
        coalesce(ap.ap_spend_gbp, 0) as ap_spend_gbp,
        coalesce(ap.supplier_cash_paid_gbp, 0) as supplier_cash_paid_gbp,
        coalesce(ap.open_ap_gbp, 0) as open_ap_gbp,
        coalesce(ap.overdue_ap_gbp, 0) as overdue_ap_gbp,

        coalesce(workforce.payroll_cost_gbp, 0) as payroll_cost_gbp,
        coalesce(workforce.active_fte, 0) as active_fte,
        coalesce(workforce.active_headcount_count, 0) as active_headcount_count,
        coalesce(financial.opex_gbp, 0) as opex_gbp,
        coalesce(financial.actual_revenue_gbp, 0) - coalesce(financial.opex_gbp, 0) as operating_profit_gbp,

        coalesce(financial.budget_revenue_gbp, 0) as budget_revenue_gbp,
        coalesce(financial.budget_opex_gbp, 0) as budget_opex_gbp,
        coalesce(financial.forecast_revenue_gbp, 0) as forecast_revenue_gbp,
        coalesce(financial.forecast_opex_gbp, 0) as forecast_opex_gbp,

        coalesce(saas.headline_arr_gbp, 0) as headline_arr_gbp,
        coalesce(saas.active_mrr_gbp, 0) as active_mrr_gbp,
        coalesce(saas.beginning_arr_gbp, 0) as beginning_arr_gbp,
        coalesce(saas.new_business_arr_gbp, 0) as new_business_arr_gbp,
        coalesce(saas.expansion_arr_gbp, 0) as expansion_arr_gbp,
        coalesce(saas.price_increase_arr_gbp, 0) as price_increase_arr_gbp,
        coalesce(saas.contraction_arr_gbp, 0) as contraction_arr_gbp,
        coalesce(saas.churn_arr_gbp, 0) as churn_arr_gbp,
        coalesce(saas.pause_arr_gbp, 0) as pause_arr_gbp,
        coalesce(saas.net_arr_delta_gbp, 0) as net_arr_delta_gbp,
        coalesce(saas.ending_arr_gbp, 0) as ending_arr_gbp,

        case
            when coalesce(retention.retention_beginning_arr_gbp, 0) > 0
                then retention.net_retained_arr_gbp / retention.retention_beginning_arr_gbp
            else null
        end as nrr,
        case
            when coalesce(retention.retention_beginning_arr_gbp, 0) > 0
                then least(greatest(retention.gross_retained_arr_gbp / retention.retention_beginning_arr_gbp, 0), 1)
            else null
        end as grr,
        case
            when coalesce(retention.beginning_active_customer_count, 0) > 0
                then cast(retention.churned_customer_count as double) / retention.beginning_active_customer_count
            else null
        end as logo_churn,

        coalesce(revenue.recognised_revenue_gbp, 0) > 0 as has_revenue_actuals,
        coalesce(o2c.billings_gbp, 0) > 0
            and coalesce(o2c.cash_collected_gbp, 0) > 0 as has_o2c_actuals,
        coalesce(financial.actual_revenue_gbp, 0) > 0
            and coalesce(financial.opex_gbp, 0) > 0 as has_financial_actuals,
        coalesce(saas.headline_arr_gbp, 0) > 0 as has_saas_actuals,

        case
            when coalesce(o2c.billings_gbp, 0) > 0
                then o2c.cash_collected_gbp / o2c.billings_gbp
            else null
        end as cash_collection_rate,
        case
            when coalesce(financial.actual_revenue_gbp, 0) > 0
                then coalesce(financial.opex_gbp, 0) / financial.actual_revenue_gbp
            else null
        end as opex_to_revenue_ratio,
        case
            when coalesce(workforce.active_fte, 0) > 0
                then coalesce(financial.actual_revenue_gbp, revenue.recognised_revenue_gbp, 0) / workforce.active_fte
            else null
        end as revenue_per_fte_gbp,

        coalesce(control_rollup.total_control_exception_count, 0) as total_control_exception_count,
        coalesce(control_rollup.model_blocking_exception_count, 0) as model_blocking_exception_count,
        coalesce(control_rollup.accepted_limitation_exception_count, 0) as accepted_limitation_exception_count,
        coalesce(control_rollup.review_exception_count, 0) as review_exception_count,
        coalesce(control_rollup.model_blocking_exception_count, 0) > 0 as has_model_blocking_controls,
        coalesce(control_rollup.total_control_exception_count, 0) > 0 as has_any_model_readiness_issue,
        control_rollup.model_blocking_control_names,
        control_rollup.accepted_limitation_control_names,
        control_rollup.review_control_names,
        case
            when coalesce(control_rollup.model_blocking_exception_count, 0) > 0 then 'Blocked'
            when coalesce(control_rollup.review_exception_count, 0) > 0 then 'Usable with review'
            when coalesce(control_rollup.accepted_limitation_exception_count, 0) > 0 then 'Accepted limitation'
            when coalesce(control_rollup.total_control_exception_count, 0) > 0 then 'Usable with review'
            else 'Ready'
        end as model_readiness_status,
        (
            not (
                coalesce(deferred.deferred_period_status, '') = 'Scheduled'
                or month_spine.reporting_month_date > date '2026-06-01'
            )
            and coalesce(revenue.recognised_revenue_gbp, 0) > 0
            and coalesce(o2c.billings_gbp, 0) > 0
            and coalesce(o2c.cash_collected_gbp, 0) > 0
            and coalesce(financial.actual_revenue_gbp, 0) > 0
            and coalesce(financial.opex_gbp, 0) > 0
            and coalesce(control_rollup.model_blocking_exception_count, 0) = 0
        ) as use_in_excel_actuals_flag,

        current_timestamp as _atlas_modelled_at

    from month_spine
    left join {{ ref('dim_date') }} as date_dim
        on month_spine.reporting_month_date = date_dim.date_day
    left join financial
        on month_spine.reporting_month_date = financial.reporting_month_date
    left join o2c
        on month_spine.reporting_month_date = o2c.reporting_month_date
    left join revenue
        on month_spine.reporting_month_date = revenue.reporting_month_date
    left join deferred
        on month_spine.reporting_month_date = deferred.reporting_month_date
    left join ap
        on month_spine.reporting_month_date = ap.reporting_month_date
    left join workforce
        on month_spine.reporting_month_date = workforce.reporting_month_date
    left join saas
        on month_spine.reporting_month_date = saas.reporting_month_date
    left join retention
        on month_spine.reporting_month_date = retention.reporting_month_date
    left join control_rollup
        on month_spine.reporting_month_date = control_rollup.reporting_month_date

)

select *
from final
