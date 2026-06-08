{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'billing', 'payment_allocations']
) }}

with source as (

    select *
    from {{ source('bronze', 'billing__billing_payment_allocations') }}

),

renamed_and_casted as (

    select
        trim(cast(allocation_pk as varchar)) as allocation_pk,
        trim(cast(allocation_id as varchar)) as allocation_id,
        trim(cast(payment_id as varchar)) as payment_id,
        trim(cast(invoice_id as varchar)) as invoice_id,
        trim(cast(customer_id as varchar)) as customer_id,

        {{ safecast_date('allocation_date') }} as allocation_date,

        upper(trim(cast(currency as varchar))) as currency,
        {{ safecast_decimal('allocated_amount_local') }} as allocated_amount_local,
        {{ safecast_decimal('allocated_amount_gbp') }} as allocated_amount_gbp,

        trim(cast(allocation_status as varchar)) as allocation_status,
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
