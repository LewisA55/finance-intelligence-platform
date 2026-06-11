{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'core_fact', 'revenue', 'deferred_revenue', 'rollforward', 'balance_sheet']
) }}

with source as (

    select
        rollforward_pk,
        period_month,
        period_status,
        currency,
        revenue_category,

        opening_deferred_revenue_local,
        new_billings_deferred_local,
        recognised_revenue_local,
        closing_deferred_revenue_local,

        opening_deferred_revenue_gbp,
        new_billings_deferred_gbp,
        recognised_revenue_gbp,
        closing_deferred_revenue_gbp,

        source_system,
        is_defect,
        defect_type,
        created_date,
        updated_date,

        _atlas_row_hash,
        _atlas_ingested_at,
        _atlas_source_file

    from {{ ref('stg_revenue__deferred_revenue_rollforward') }}

),

with_calculations as (

    select
        s.*,

        round(
            coalesce(s.opening_deferred_revenue_local, 0)
            + coalesce(s.new_billings_deferred_local, 0)
            - coalesce(s.recognised_revenue_local, 0)
            - coalesce(s.closing_deferred_revenue_local, 0),
            2
        ) as rollforward_variance_local,

        round(
            coalesce(s.opening_deferred_revenue_gbp, 0)
            + coalesce(s.new_billings_deferred_gbp, 0)
            - coalesce(s.recognised_revenue_gbp, 0)
            - coalesce(s.closing_deferred_revenue_gbp, 0),
            2
        ) as rollforward_variance_gbp,

        lag(coalesce(s.closing_deferred_revenue_local, 0)) over (
            partition by
                coalesce(nullif(trim(upper(cast(s.currency as varchar))), ''), 'UNKNOWN'),
                coalesce(nullif(trim(cast(s.revenue_category as varchar)), ''), 'Unknown')
            order by s.period_month
        ) as prior_closing_deferred_revenue_local,

        lag(coalesce(s.closing_deferred_revenue_gbp, 0)) over (
            partition by
                coalesce(nullif(trim(upper(cast(s.currency as varchar))), ''), 'UNKNOWN'),
                coalesce(nullif(trim(cast(s.revenue_category as varchar)), ''), 'Unknown')
            order by s.period_month
        ) as prior_closing_deferred_revenue_gbp

    from source as s

),

renamed as (

    select
        md5(trim(upper(cast(rollforward_pk as varchar)))) as deferred_revenue_rollforward_hk,

        rollforward_pk,

        case
            when period_month is not null
            then md5(strftime(period_month, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as period_month_date_hk,

        case
            when revenue_category = 'Subscription Revenue' then md5('2100')
            else md5('UNASSIGNED_GL_ACCOUNT')
        end as gl_account_hk,

        case
            when revenue_category = 'Subscription Revenue' then '2100'
            else 'UNASSIGNED'
        end as mapped_account_code,

        case
            when revenue_category = 'Subscription Revenue' then 'Deferred revenue category fallback'
            else 'Unassigned fallback'
        end as deferred_revenue_account_mapping_method,

        period_month,
        coalesce(nullif(trim(cast(period_status as varchar)), ''), 'Unknown') as period_status,
        coalesce(nullif(trim(upper(cast(currency as varchar))), ''), 'UNKNOWN') as currency_code,
        coalesce(nullif(trim(cast(revenue_category as varchar)), ''), 'Unknown') as revenue_category,

        coalesce(opening_deferred_revenue_local, 0) as opening_deferred_revenue_local,
        coalesce(new_billings_deferred_local, 0) as new_billings_deferred_local,
        coalesce(recognised_revenue_local, 0) as recognised_revenue_local,
        coalesce(closing_deferred_revenue_local, 0) as closing_deferred_revenue_local,

        coalesce(opening_deferred_revenue_gbp, 0) as opening_deferred_revenue_gbp,
        coalesce(new_billings_deferred_gbp, 0) as new_billings_deferred_gbp,
        coalesce(recognised_revenue_gbp, 0) as recognised_revenue_gbp,
        coalesce(closing_deferred_revenue_gbp, 0) as closing_deferred_revenue_gbp,

        rollforward_variance_local,
        rollforward_variance_gbp,

        prior_closing_deferred_revenue_local,
        prior_closing_deferred_revenue_gbp,

        case
            when prior_closing_deferred_revenue_local is null then 0
            else round(
                coalesce(opening_deferred_revenue_local, 0)
                - coalesce(prior_closing_deferred_revenue_local, 0),
                2
            )
        end as continuity_variance_local,

        case
            when prior_closing_deferred_revenue_gbp is null then 0
            else round(
                coalesce(opening_deferred_revenue_gbp, 0)
                - coalesce(prior_closing_deferred_revenue_gbp, 0),
                2
            )
        end as continuity_variance_gbp,

        case
            when abs(rollforward_variance_local) > 0.01
              or abs(rollforward_variance_gbp) > 0.01
            then true
            else false
        end as is_rollforward_arithmetic_exception,

        case
            when prior_closing_deferred_revenue_gbp is not null
             and (
                    abs(
                        round(
                            coalesce(opening_deferred_revenue_local, 0)
                            - coalesce(prior_closing_deferred_revenue_local, 0),
                            2
                        )
                    ) > 0.01
                 or abs(
                        round(
                            coalesce(opening_deferred_revenue_gbp, 0)
                            - coalesce(prior_closing_deferred_revenue_gbp, 0),
                            2
                        )
                    ) > 0.01
                )
            then true
            else false
        end as is_period_continuity_exception,

        case
            when coalesce(closing_deferred_revenue_local, 0) < 0
              or coalesce(closing_deferred_revenue_gbp, 0) < 0
            then true
            else false
        end as is_negative_closing_deferred_revenue,

        case when period_status = 'Actual' then true else false end as is_actual_period,
        case when period_status = 'Scheduled' then true else false end as is_scheduled_period,

        coalesce(is_defect, false) as is_defect,
        nullif(trim(cast(defect_type as varchar)), '') as defect_type,

        source_system,
        created_date,
        updated_date,

        _atlas_row_hash,
        _atlas_ingested_at,
        _atlas_source_file

    from with_calculations

)

select *
from renamed
