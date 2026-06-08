{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'billing', 'invoices']
) }}

with source as (

    select *
    from {{ source('bronze', 'billing__billing_invoices') }}

),

renamed_and_casted as (

    select
        trim(cast(invoice_pk as varchar)) as invoice_pk,
        trim(cast(invoice_id as varchar)) as invoice_id,
        trim(cast(customer_id as varchar)) as customer_id,

        {{ safecast_date('invoice_date') }} as invoice_date,
        {{ safecast_date('billing_period_start') }} as billing_period_start_date,
        {{ safecast_date('billing_period_end') }} as billing_period_end_date,
        {{ safecast_date('due_date') }} as due_date,

        trim(cast(payment_terms as varchar)) as payment_terms,
        trim(cast(invoice_status as varchar)) as invoice_status,
        upper(trim(cast(currency as varchar))) as currency,

        {{ safecast_decimal('subtotal_local') }} as subtotal_local,
        {{ safecast_decimal('tax_rate', 9, 4) }} as tax_rate,
        {{ safecast_decimal('tax_amount_local') }} as tax_amount_local,
        {{ safecast_decimal('total_local') }} as total_local,

        {{ safecast_decimal('subtotal_gbp') }} as subtotal_gbp,
        {{ safecast_decimal('tax_amount_gbp') }} as tax_amount_gbp,
        {{ safecast_decimal('total_gbp') }} as total_gbp,

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
