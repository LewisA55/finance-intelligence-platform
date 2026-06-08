{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'billing', 'payments']
) }}

with source as (

    select *
    from {{ source('bronze', 'billing__billing_payments') }}

),

renamed_and_casted as (

    select
        trim(cast(payment_pk as varchar)) as payment_pk,
        trim(cast(payment_id as varchar)) as payment_id,
        trim(cast(customer_id as varchar)) as customer_id,

        {{ safecast_date('payment_date') }} as payment_date,
        trim(cast(payment_method as varchar)) as payment_method,
        nullif(trim(cast(payment_reference as varchar)), '') as payment_reference,

        upper(trim(cast(currency as varchar))) as currency,
        {{ safecast_decimal('payment_amount_local') }} as payment_amount_local,
        {{ safecast_decimal('payment_amount_gbp') }} as payment_amount_gbp,

        trim(cast(bank_account_region as varchar)) as bank_account_region,
        trim(cast(payment_status as varchar)) as payment_status,
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
