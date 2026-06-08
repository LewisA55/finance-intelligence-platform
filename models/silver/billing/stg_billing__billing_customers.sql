{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'billing', 'customers']
) }}

with source as (

    select *
    from {{ source('bronze', 'billing__billing_customers') }}

),

renamed_and_casted as (

    select
        -- Primary key / identifiers
        trim(cast(customer_pk as varchar)) as customer_pk,
        trim(cast(customer_id as varchar)) as customer_id,
        nullif(trim(cast(legacy_id as varchar)), '') as legacy_id,

        -- Customer attributes
        trim(cast(customer_name as varchar)) as customer_name,
        trim(cast(customer_segment as varchar)) as customer_segment,
        trim(cast(industry as varchar)) as industry,
        trim(cast(region_id as varchar)) as region_id,
        upper(trim(cast(currency_code as varchar))) as currency_code,
        cast(try_cast(nullif(trim(cast(cohort_year as varchar)), '') as integer) as integer) as cohort_year,

        -- Acquisition attributes
        {{ safecast_boolean('is_acquired_customer') }} as is_acquired_customer,
        nullif(trim(cast(acquisition_source as varchar)), '') as acquisition_source,

        -- Lifecycle attributes
        {{ safecast_date('created_date') }} as created_date,
        trim(cast(customer_status as varchar)) as customer_status,
        {{ safecast_boolean('active_flag') }} as is_active,

        -- Atlas Bronze lineage metadata
        _atlas_row_hash,
        cast(_atlas_ingested_at as timestamp) as _atlas_ingested_at,
        _atlas_source_file

    from source

)

select *
from renamed_and_casted
