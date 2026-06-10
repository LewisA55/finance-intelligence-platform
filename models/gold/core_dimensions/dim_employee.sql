{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'core_dimension', 'employee']
) }}

with employee_master as (

    select
        trim(upper(cast(employee_id as varchar))) as employee_id,
        employee_pk,
        nullif(trim(cast(employee_name as varchar)), '') as employee_name,

        coalesce(nullif(trim(upper(cast(department_id as varchar))), ''), 'UNASSIGNED') as department_id,
        md5(coalesce(nullif(trim(upper(cast(department_id as varchar))), ''), 'UNASSIGNED')) as department_hk,
        coalesce(nullif(trim(upper(cast(department_code as varchar))), ''), 'UNASSIGNED') as department_code,
        coalesce(nullif(trim(cast(functional_group as varchar)), ''), 'Unknown') as functional_group,

        coalesce(nullif(trim(upper(cast(region_id as varchar))), ''), 'UNASSIGNED') as region_id,
        md5(coalesce(nullif(trim(upper(cast(region_id as varchar))), ''), 'UNASSIGNED')) as region_hk,
        coalesce(nullif(trim(upper(cast(currency_code as varchar))), ''), 'UNKNOWN') as currency_code,

        coalesce(nullif(trim(cast(job_level as varchar)), ''), 'Unknown') as job_level,
        coalesce(nullif(trim(cast(job_title as varchar)), ''), 'Unknown') as job_title,

        nullif(trim(upper(cast(manager_employee_id as varchar))), '') as manager_employee_id,
        md5(coalesce(nullif(trim(upper(cast(manager_employee_id as varchar))), ''), 'UNASSIGNED')) as manager_employee_hk,

        hire_date,
        termination_date,
        coalesce(nullif(trim(cast(employment_status as varchar)), ''), 'Unknown') as employment_status,

        base_salary_local,
        base_salary_gbp,
        salary_multiplier,

        coalesce(is_sales_employee, false) as is_sales_employee,
        coalesce(is_ghost_headcount, false) as is_ghost_headcount,
        coalesce(has_data_quality_issue, false) as has_data_quality_issue,
        coalesce(nullif(trim(cast(data_quality_issue as varchar)), ''), 'None') as data_quality_issue,
        coalesce(is_active, false) as is_active,

        _atlas_row_hash,
        _atlas_ingested_at,
        _atlas_source_file

    from {{ ref('stg_hris__hr_employees') }}
    where employee_id is not null
      and trim(employee_id) <> ''

),

headcount_snapshot as (

    select
        trim(upper(cast(employee_id as varchar))) as employee_id,
        count(*) as headcount_snapshot_rows
    from {{ ref('stg_hris__hr_headcount_snapshot') }}
    where employee_id is not null
      and trim(employee_id) <> ''
    group by trim(upper(cast(employee_id as varchar)))

),

employee_compensation as (

    select
        trim(upper(cast(employee_id as varchar))) as employee_id,
        count(*) as employee_compensation_rows
    from {{ ref('stg_workforce__employee_compensation') }}
    where employee_id is not null
      and trim(employee_id) <> ''
    group by trim(upper(cast(employee_id as varchar)))

),

headcount_plan as (

    select
        trim(upper(cast(employee_id as varchar))) as employee_id,
        count(*) as headcount_plan_rows
    from {{ ref('stg_workforce__headcount_plan') }}
    where employee_id is not null
      and trim(employee_id) <> ''
    group by trim(upper(cast(employee_id as varchar)))

),

employee_rows as (

    select
        md5(trim(upper(m.employee_id))) as employee_hk,

        m.employee_pk,
        m.employee_id,
        m.employee_name,

        m.department_id,
        m.department_hk,
        m.department_code,
        m.functional_group,

        m.region_id,
        m.region_hk,
        m.currency_code,

        m.job_level,
        m.job_title,

        m.manager_employee_id,
        m.manager_employee_hk,

        m.hire_date,
        m.termination_date,
        m.employment_status,

        case when m.employment_status = 'Active' and m.is_active = true then true else false end as is_active_employee,
        case when m.employment_status = 'Terminated' or m.termination_date is not null then true else false end as is_terminated_employee,

        m.base_salary_local,
        m.base_salary_gbp,
        m.salary_multiplier,

        m.is_sales_employee,
        m.is_ghost_headcount,
        m.has_data_quality_issue,
        m.data_quality_issue,

        case
            when upper(m.employee_id) like '%UNKNOWN%'
              or upper(coalesce(m.employee_name, '')) like '%UNKNOWN%'
            then true
            else false
        end as is_unknown_employee,

        case when coalesce(h.headcount_snapshot_rows, 0) > 0 then true else false end as exists_in_headcount_snapshot,
        case when coalesce(c.employee_compensation_rows, 0) > 0 then true else false end as exists_in_employee_compensation,
        case when coalesce(p.headcount_plan_rows, 0) > 0 then true else false end as exists_in_headcount_plan,

        coalesce(h.headcount_snapshot_rows, 0) as headcount_snapshot_rows,
        coalesce(c.employee_compensation_rows, 0) as employee_compensation_rows,
        coalesce(p.headcount_plan_rows, 0) as headcount_plan_rows,

        case
            when m.job_level = 'Analyst' then 10
            when m.job_level = 'Manager' then 20
            when m.job_level = 'Senior Manager' then 30
            when m.job_level = 'Director' then 40
            when m.job_level = 'VP' then 50
            else 99
        end as job_level_sort,

        case
            when m.employment_status = 'Active' then 10
            when m.employment_status = 'Terminated' then 20
            else 99
        end as employment_status_sort,

        m._atlas_row_hash,
        m._atlas_ingested_at,
        m._atlas_source_file,

        false as is_unassigned

    from employee_master as m
    left join headcount_snapshot as h
        on m.employee_id = h.employee_id
    left join employee_compensation as c
        on m.employee_id = c.employee_id
    left join headcount_plan as p
        on m.employee_id = p.employee_id

),

unassigned_row as (

    select
        md5('UNASSIGNED') as employee_hk,

        'UNASSIGNED_EMPLOYEE' as employee_pk,
        'UNASSIGNED' as employee_id,
        'Unassigned Employee' as employee_name,

        'UNASSIGNED' as department_id,
        md5('UNASSIGNED') as department_hk,
        'UNASSIGNED' as department_code,
        'Unassigned' as functional_group,

        'UNASSIGNED' as region_id,
        md5('UNASSIGNED') as region_hk,
        'UNASSIGNED' as currency_code,

        'Unassigned' as job_level,
        'Unassigned' as job_title,

        cast(null as varchar) as manager_employee_id,
        md5('UNASSIGNED') as manager_employee_hk,

        cast(null as date) as hire_date,
        cast(null as date) as termination_date,
        'Unassigned' as employment_status,

        false as is_active_employee,
        false as is_terminated_employee,

        cast(null as decimal(18,4)) as base_salary_local,
        cast(null as decimal(18,4)) as base_salary_gbp,
        cast(null as decimal(18,4)) as salary_multiplier,

        false as is_sales_employee,
        false as is_ghost_headcount,
        false as has_data_quality_issue,
        'None' as data_quality_issue,

        false as is_unknown_employee,

        false as exists_in_headcount_snapshot,
        false as exists_in_employee_compensation,
        false as exists_in_headcount_plan,

        0 as headcount_snapshot_rows,
        0 as employee_compensation_rows,
        0 as headcount_plan_rows,

        -1 as job_level_sort,
        -1 as employment_status_sort,

        cast(null as varchar) as _atlas_row_hash,
        cast(null as timestamp) as _atlas_ingested_at,
        cast(null as varchar) as _atlas_source_file,

        true as is_unassigned

)

select *
from unassigned_row

union all

select *
from employee_rows
