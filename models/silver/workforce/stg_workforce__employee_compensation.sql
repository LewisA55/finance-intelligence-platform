{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'workforce', 'compensation']
) }}

with source as (

    select *
    from {{ source('bronze', 'workforce__employee_compensation') }}

),

renamed_and_casted as (

    select
        trim(cast(compensation_pk as varchar)) as compensation_pk,
        trim(cast(compensation_line_id as varchar)) as compensation_line_id,

        trim(cast(employee_id as varchar)) as employee_id,

        cast(date_trunc('month', {{ safecast_date('period_start_date') }}) as date) as posting_period,
        {{ safecast_date('period_start_date') }} as period_start_date,
        {{ safecast_date('period_end_date') }} as period_end_date,

        trim(cast(department_id as varchar)) as department_id,
        trim(cast(region_id as varchar)) as region_id,
        upper(trim(cast(country_code as varchar))) as country_code,
        upper(trim(cast(currency as varchar))) as currency,

        trim(cast(compensation_component as varchar)) as compensation_component,

        {{ safecast_decimal('annual_base_salary_local') }} as annual_base_salary_local,
        {{ safecast_decimal('monthly_base_salary_local') }} as monthly_base_salary_local,
        {{ safecast_decimal('component_rate') }} as component_rate,
        {{ safecast_decimal('amount_local') }} as amount_local,
        {{ safecast_decimal('amount_gbp') }} as amount_gbp,
        {{ safecast_decimal('fx_rate_to_gbp') }} as fx_rate_to_gbp,

        trim(cast(source_system as varchar)) as source_system,
        {{ safecast_boolean('is_system_generated') }} as is_system_generated,
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
