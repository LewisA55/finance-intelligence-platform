{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'hris', 'headcount']
) }}

with source as (

    select *
    from {{ source('bronze', 'hris__hr_headcount_snapshot') }}

),

renamed_and_casted as (

    select
        trim(cast(employee_id as varchar)) as employee_id,

        {{ safecast_date('snapshot_month') }} as snapshot_month,

        trim(cast(department_id as varchar)) as department_id,
        trim(cast(department_code as varchar)) as department_code,
        trim(cast(functional_group as varchar)) as functional_group,

        trim(cast(region_id as varchar)) as region_id,
        upper(trim(cast(currency_code as varchar))) as currency_code,

        trim(cast(job_level as varchar)) as job_level,
        trim(cast(employment_status as varchar)) as employment_status,

        {{ safecast_decimal('monthly_salary_local') }} as monthly_salary_local,
        {{ safecast_decimal('monthly_salary_gbp') }} as monthly_salary_gbp,
        {{ safecast_decimal('fte_count') }} as fte_count,

        {{ safecast_boolean('is_active_flag') }} as is_active,
        {{ safecast_boolean('is_ghost_headcount') }} as is_ghost_headcount,

        _atlas_row_hash,
        cast(_atlas_ingested_at as timestamp) as _atlas_ingested_at,
        _atlas_source_file

    from source

)

select *
from renamed_and_casted
