{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'billing', 'invoice_lines']
) }}

with source as (

    select *
    from {{ source('bronze', 'billing__billing_invoice_lines') }}

),

renamed_and_casted as (

    select
        trim(cast(invoice_line_pk as varchar)) as invoice_line_pk,
        trim(cast(invoice_line_id as varchar)) as invoice_line_id,
        trim(cast(invoice_id as varchar)) as invoice_id,
        trim(cast(subscription_id as varchar)) as subscription_id,
        trim(cast(customer_id as varchar)) as customer_id,
        trim(cast(product_id as varchar)) as product_id,

        trim(cast(line_type as varchar)) as line_type,
        {{ safecast_date('service_period_start') }} as service_period_start_date,
        {{ safecast_date('service_period_end') }} as service_period_end_date,
        trim(cast(billing_frequency as varchar)) as billing_frequency,

        {{ safecast_decimal('quantity') }} as quantity,
        {{ safecast_decimal('unit_price_local') }} as unit_price_local,
        {{ safecast_decimal('line_amount_local') }} as line_amount_local,
        {{ safecast_decimal('unit_price_gbp') }} as unit_price_gbp,
        {{ safecast_decimal('line_amount_gbp') }} as line_amount_gbp,

        upper(trim(cast(currency as varchar))) as currency,
        trim(cast(revenue_category as varchar)) as revenue_category,

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
