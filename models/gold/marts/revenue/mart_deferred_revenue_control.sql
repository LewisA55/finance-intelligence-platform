{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'mart', 'revenue', 'deferred_revenue', 'control', 'balance_sheet', 'cfo']
) }}

with source as (

    select
        period_month_date_hk,
        period_month,
        period_status,
        currency_code,
        revenue_category,
        gl_account_hk,
        mapped_account_code,
        deferred_revenue_account_mapping_method,

        opening_deferred_revenue_local,
        new_billings_deferred_local,
        recognised_revenue_local,
        closing_deferred_revenue_local,

        opening_deferred_revenue_gbp,
        new_billings_deferred_gbp,
        recognised_revenue_gbp,
        closing_deferred_revenue_gbp,

        rollforward_variance_local,
        rollforward_variance_gbp,
        prior_closing_deferred_revenue_local,
        prior_closing_deferred_revenue_gbp,
        continuity_variance_local,
        continuity_variance_gbp,

        is_rollforward_arithmetic_exception,
        is_period_continuity_exception,
        is_negative_closing_deferred_revenue,
        is_actual_period,
        is_scheduled_period,
        is_defect,
        defect_type,
        source_system

    from {{ ref('fct_deferred_revenue_rollforward') }}

),

aggregated as (

    select
        md5(
            coalesce(period_month_date_hk, md5('UNASSIGNED'))
            || '|'
            || coalesce(period_status, 'Unknown')
            || '|'
            || coalesce(currency_code, 'UNKNOWN')
            || '|'
            || coalesce(revenue_category, 'Unknown')
        ) as deferred_revenue_control_hk,

        period_month_date_hk,
        period_month,
        period_status,
        currency_code,
        revenue_category,

        max(gl_account_hk) as gl_account_hk,
        max(mapped_account_code) as mapped_account_code,
        max(deferred_revenue_account_mapping_method) as deferred_revenue_account_mapping_method,

        count(*) as rollforward_row_count,

        round(sum(opening_deferred_revenue_local), 2) as corporate_opening_deferred_revenue_local,
        round(sum(new_billings_deferred_local), 2) as corporate_new_billings_deferred_local,
        round(sum(recognised_revenue_local), 2) as corporate_recognised_revenue_local,
        round(sum(closing_deferred_revenue_local), 2) as corporate_closing_deferred_revenue_local,

        round(sum(opening_deferred_revenue_gbp), 2) as corporate_opening_deferred_revenue_gbp,
        round(sum(new_billings_deferred_gbp), 2) as corporate_new_billings_deferred_gbp,
        round(sum(recognised_revenue_gbp), 2) as corporate_recognised_revenue_gbp,
        round(sum(closing_deferred_revenue_gbp), 2) as corporate_closing_deferred_revenue_gbp,

        round(sum(rollforward_variance_local), 2) as corporate_rollforward_variance_local,
        round(sum(rollforward_variance_gbp), 2) as corporate_rollforward_variance_gbp,

        round(sum(continuity_variance_local), 2) as corporate_continuity_variance_local,
        round(sum(continuity_variance_gbp), 2) as corporate_continuity_variance_gbp,

        round(sum(coalesce(prior_closing_deferred_revenue_local, 0)), 2) as corporate_prior_closing_deferred_revenue_local,
        round(sum(coalesce(prior_closing_deferred_revenue_gbp, 0)), 2) as corporate_prior_closing_deferred_revenue_gbp,

        sum(case when is_rollforward_arithmetic_exception then 1 else 0 end) as corporate_rollforward_exception_count,
        sum(case when is_period_continuity_exception then 1 else 0 end) as corporate_continuity_exception_count,
        sum(case when is_negative_closing_deferred_revenue then 1 else 0 end) as corporate_negative_closing_deferred_revenue_count,
        sum(case when is_defect then 1 else 0 end) as corporate_defect_row_count,

        case
            when sum(case when is_rollforward_arithmetic_exception then 1 else 0 end) > 0
            then true else false
        end as has_rollforward_arithmetic_exception,

        case
            when sum(case when is_period_continuity_exception then 1 else 0 end) > 0
            then true else false
        end as has_period_continuity_exception,

        case
            when sum(case when is_negative_closing_deferred_revenue then 1 else 0 end) > 0
            then true else false
        end as has_negative_closing_deferred_revenue,

        case
            when sum(case when is_defect then 1 else 0 end) > 0
            then true else false
        end as has_source_defect,

        case
            when sum(case when is_rollforward_arithmetic_exception then 1 else 0 end) > 0
              or sum(case when is_period_continuity_exception then 1 else 0 end) > 0
              or sum(case when is_negative_closing_deferred_revenue then 1 else 0 end) > 0
              or sum(case when is_defect then 1 else 0 end) > 0
            then true else false
        end as has_deferred_revenue_control_exception,

        max(case when is_actual_period then true else false end) as is_actual_period,
        max(case when is_scheduled_period then true else false end) as is_scheduled_period,

        string_agg(distinct defect_type, ', ' order by defect_type) filter (
            where defect_type is not null
        ) as defect_types,

        string_agg(distinct source_system, ', ' order by source_system) as source_systems,

        current_timestamp as _atlas_modelled_at

    from source

    group by
        period_month_date_hk,
        period_month,
        period_status,
        currency_code,
        revenue_category

)

select *
from aggregated
