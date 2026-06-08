{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'revenue', 'deferred_revenue']
) }}

with source as (

    select *
    from {{ source('bronze', 'revenue__deferred_revenue_rollforward') }}

),

renamed_and_casted as (

    select
        trim(cast(rollforward_pk as varchar)) as rollforward_pk,

        {{ safecast_date('period_month') }} as period_month,
        trim(cast(period_status as varchar)) as period_status,

        upper(trim(cast(currency as varchar))) as currency,
        trim(cast(revenue_category as varchar)) as revenue_category,

        {{ safecast_decimal('opening_deferred_revenue_local') }} as opening_deferred_revenue_local,
        {{ safecast_decimal('new_billings_deferred_local') }} as new_billings_deferred_local,
        {{ safecast_decimal('recognised_revenue_local') }} as recognised_revenue_local,
        {{ safecast_decimal('closing_deferred_revenue_local') }} as closing_deferred_revenue_local,

        {{ safecast_decimal('opening_deferred_revenue_gbp') }} as opening_deferred_revenue_gbp,
        {{ safecast_decimal('new_billings_deferred_gbp') }} as new_billings_deferred_gbp,
        {{ safecast_decimal('recognised_revenue_gbp') }} as recognised_revenue_gbp,
        {{ safecast_decimal('closing_deferred_revenue_gbp') }} as closing_deferred_revenue_gbp,

        trim(cast(source_system as varchar)) as source_system,
        {{ safecast_boolean('is_defect_flag') }} as is_defect,
        nullif(trim(cast(defect_type as varchar)), '') as defect_type,

        {{ safecast_date('created_at') }} as created_date,
        {{ safecast_date('updated_at') }} as updated_date,

        _atlas_row_hash,
        cast(_atlas_ingested_at as timestamp) as _atlas_ingested_at,
        _atlas_source_file

    from source

)

select *
from renamed_and_casted
