{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'hris', 'employees']
) }}

with source as (

    select *
    from {{ source('bronze', 'hris__hr_employees') }}

),

renamed_and_casted as (

    select
        trim(cast(employee_pk as varchar)) as employee_pk,
        trim(cast(employee_id as varchar)) as employee_id,
        trim(cast(employee_name as varchar)) as employee_name,

        trim(cast(department_id as varchar)) as department_id,
        trim(cast(department_code as varchar)) as department_code,
        trim(cast(functional_group as varchar)) as functional_group,

        trim(cast(region_id as varchar)) as region_id,
        upper(trim(cast(currency_code as varchar))) as currency_code,

        trim(cast(job_level as varchar)) as job_level,
        trim(cast(job_title as varchar)) as job_title,

        nullif(trim(cast(manager_employee_id as varchar)), '') as manager_employee_id,

        {{ safecast_date('hire_date') }} as hire_date,
        {{ safecast_date('termination_date') }} as termination_date,

        trim(cast(employment_status as varchar)) as employment_status,

        {{ safecast_decimal('base_salary_local') }} as base_salary_local,
        {{ safecast_decimal('base_salary_gbp') }} as base_salary_gbp,
        {{ safecast_decimal('salary_multiplier') }} as salary_multiplier,

        {{ safecast_boolean('is_sales_employee') }} as is_sales_employee,
        {{ safecast_boolean('is_ghost_headcount') }} as is_ghost_headcount,

        {{ safecast_boolean('data_quality_flag') }} as has_data_quality_issue,
        nullif(trim(cast(data_quality_issue as varchar)), '') as data_quality_issue,

        {{ safecast_boolean('active_flag') }} as is_active,

        _atlas_row_hash,
        cast(_atlas_ingested_at as timestamp) as _atlas_ingested_at,
        _atlas_source_file

    from source

)

select *
from renamed_and_casted
