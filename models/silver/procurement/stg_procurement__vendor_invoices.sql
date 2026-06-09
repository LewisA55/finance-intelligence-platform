{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'procurement', 'ap', 'vendor_invoices']
) }}

with source as (

    select *
    from {{ source('bronze', 'procurement__vendor_invoices') }}

),

renamed_and_casted as (

    select
        trim(cast(vendor_invoice_pk as varchar)) as vendor_invoice_pk,
        trim(cast(vendor_invoice_id as varchar)) as vendor_invoice_id,

        trim(cast(vendor_id as varchar)) as vendor_id,
        trim(cast(vendor_name as varchar)) as vendor_name,
        trim(cast(invoice_number as varchar)) as invoice_number,

        {{ safecast_date('invoice_date') }} as invoice_date,
        {{ safecast_date('due_date') }} as due_date,
        {{ safecast_date('posting_date') }} as posting_date,
        cast(date_trunc('month', {{ safecast_date('posting_date') }}) as date) as posting_period,

        upper(trim(cast(currency as varchar))) as currency,

        {{ safecast_decimal('subtotal_local') }} as subtotal_local,
        {{ safecast_decimal('tax_rate') }} as tax_rate,
        {{ safecast_decimal('tax_amount_local') }} as tax_amount_local,
        {{ safecast_decimal('total_local') }} as total_local,

        {{ safecast_decimal('subtotal_gbp') }} as subtotal_gbp,
        {{ safecast_decimal('tax_amount_gbp') }} as tax_amount_gbp,
        {{ safecast_decimal('total_gbp') }} as total_gbp,

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
