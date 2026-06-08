{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'revenue', 'revenue_recognition']
) }}

with source as (

    select *
    from {{ source('bronze', 'revenue__revenue_recognition_schedule') }}

),

renamed_and_casted as (

    select
        trim(cast(revenue_recognition_pk as varchar)) as revenue_recognition_pk,
        trim(cast(recognition_id as varchar)) as recognition_id,

        trim(cast(invoice_id as varchar)) as invoice_id,
        trim(cast(invoice_line_id as varchar)) as invoice_line_id,
        trim(cast(customer_id as varchar)) as customer_id,
        trim(cast(subscription_id as varchar)) as subscription_id,
        trim(cast(product_id as varchar)) as product_id,

        {{ safecast_date('recognition_month') }} as recognition_month,
        {{ safecast_date('service_period_start') }} as service_period_start_date,
        {{ safecast_date('service_period_end') }} as service_period_end_date,
        {{ safecast_date('recognition_start_date') }} as recognition_start_date,
        {{ safecast_date('recognition_end_date') }} as recognition_end_date,

        cast(try_cast(nullif(trim(cast(days_in_service_period as varchar)), '') as integer) as integer) as days_in_service_period,
        cast(try_cast(nullif(trim(cast(days_recognised_in_month as varchar)), '') as integer) as integer) as days_recognised_in_month,

        upper(trim(cast(currency as varchar))) as currency,

        {{ safecast_decimal('invoice_line_amount_local') }} as invoice_line_amount_local,
        {{ safecast_decimal('invoice_line_amount_gbp') }} as invoice_line_amount_gbp,
        {{ safecast_decimal('recognised_revenue_local') }} as recognised_revenue_local,
        {{ safecast_decimal('recognised_revenue_gbp') }} as recognised_revenue_gbp,
        {{ safecast_decimal('deferred_revenue_local_after_month') }} as deferred_revenue_local_after_month,
        {{ safecast_decimal('deferred_revenue_gbp_after_month') }} as deferred_revenue_gbp_after_month,

        trim(cast(revenue_category as varchar)) as revenue_category,
        trim(cast(recognition_method as varchar)) as recognition_method,
        trim(cast(recognition_status as varchar)) as recognition_status,

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
