{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'billing', 'subscriptions']
) }}

with source as (

    select *
    from {{ source('bronze', 'billing__billing_subscriptions') }}

),

renamed_and_casted as (

    select
        trim(cast(subscription_pk as varchar)) as subscription_pk,
        trim(cast(subscription_id as varchar)) as subscription_id,
        trim(cast(customer_id as varchar)) as customer_id,
        trim(cast(product_id as varchar)) as product_id,

        trim(cast(customer_segment as varchar)) as customer_segment,
        trim(cast(plan_tier as varchar)) as plan_tier,

        {{ safecast_date('contract_start_date') }} as contract_start_date,
        {{ safecast_date('contract_end_date') }} as contract_end_date,
        cast(try_cast(nullif(trim(cast(contract_term_months as varchar)), '') as integer) as integer) as contract_term_months,
        trim(cast(billing_frequency as varchar)) as billing_frequency,
        cast(try_cast(nullif(trim(cast(billing_anchor_day as varchar)), '') as integer) as integer) as billing_anchor_day,
        trim(cast(contract_status as varchar)) as contract_status,

        {{ safecast_decimal('mrr_local') }} as mrr_local,
        {{ safecast_decimal('mrr_gbp') }} as mrr_gbp,
        {{ safecast_decimal('arr_local') }} as arr_local,
        {{ safecast_decimal('arr_gbp') }} as arr_gbp,
        upper(trim(cast(currency as varchar))) as currency,

        trim(cast(payment_terms as varchar)) as payment_terms,
        {{ safecast_boolean('auto_renew_flag') }} as is_auto_renew,
        {{ safecast_decimal('discount_pct', 9, 4) }} as discount_pct,
        trim(cast(price_source as varchar)) as price_source,
        nullif(trim(cast(acquisition_source as varchar)), '') as acquisition_source,

        trim(cast(source_system as varchar)) as source_system,
        {{ safecast_date('created_at') }} as created_date,
        {{ safecast_date('updated_at') }} as updated_date,
        {{ safecast_boolean('is_defect_flag') }} as is_defect,
        nullif(trim(cast(defect_type as varchar)), '') as defect_type,

        _atlas_row_hash,
        cast(_atlas_ingested_at as timestamp) as _atlas_ingested_at,
        _atlas_source_file

    from source

)

select *
from renamed_and_casted
