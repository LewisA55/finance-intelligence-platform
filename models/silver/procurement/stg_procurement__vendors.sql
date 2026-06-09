{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'procurement', 'vendors']
) }}

with source as (

    select *
    from {{ source('bronze', 'procurement__vendors') }}

),

renamed_and_casted as (

    select
        trim(cast(vendor_pk as varchar)) as vendor_pk,
        trim(cast(vendor_id as varchar)) as vendor_id,
        trim(cast(vendor_name as varchar)) as vendor_name,

        trim(cast(vendor_category as varchar)) as vendor_category,

        trim(cast(default_account_code as varchar)) as default_account_code,
        trim(cast(default_department_id as varchar)) as default_department_id,
        trim(cast(region_id as varchar)) as region_id,

        upper(trim(cast(currency as varchar))) as currency,
        trim(cast(cash_account_code as varchar)) as cash_account_code,

        trim(cast(payment_terms as varchar)) as payment_terms,
        trim(cast(vendor_status as varchar)) as vendor_status,
        trim(cast(approval_status as varchar)) as approval_status,

        {{ safecast_boolean('is_strategic_vendor') }} as is_strategic_vendor,
        {{ safecast_boolean('is_recurring_vendor') }} as is_recurring_vendor,

        trim(cast(risk_rating as varchar)) as risk_rating,

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
