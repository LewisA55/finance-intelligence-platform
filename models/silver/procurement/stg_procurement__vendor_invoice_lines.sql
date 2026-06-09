{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'procurement', 'ap', 'vendor_invoice_lines']
) }}

with source as (

    select *
    from {{ source('bronze', 'procurement__vendor_invoice_lines') }}

),

renamed_and_casted as (

    select
        trim(cast(vendor_invoice_line_pk as varchar)) as vendor_invoice_line_pk,
        trim(cast(vendor_invoice_line_id as varchar)) as vendor_invoice_line_id,

        trim(cast(vendor_invoice_id as varchar)) as vendor_invoice_id,
        trim(cast(vendor_id as varchar)) as vendor_id,
        trim(cast(vendor_name as varchar)) as vendor_name,

        cast(try_cast(nullif(trim(cast(line_number as varchar)), '') as integer) as integer) as line_number,

        trim(cast(account_code as varchar)) as account_code,
        trim(cast(expense_category as varchar)) as expense_category,

        {{ safecast_date('service_period_start') }} as service_period_start_date,
        {{ safecast_date('service_period_end') }} as service_period_end_date,

        nullif(trim(cast(line_description as varchar)), '') as line_description,

        {{ safecast_decimal('line_amount_local') }} as line_amount_local,
        {{ safecast_decimal('line_amount_gbp') }} as line_amount_gbp,

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
