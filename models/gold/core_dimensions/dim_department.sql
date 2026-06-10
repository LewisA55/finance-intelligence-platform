{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'core_dimension', 'department']
) }}

with hris_employees as (

    select
        trim(cast(department_id as varchar)) as department_id,
        trim(cast(department_code as varchar)) as department_code,
        trim(cast(functional_group as varchar)) as functional_group,
        count(*) as hris_employee_rows
    from {{ ref('stg_hris__hr_employees') }}
    where department_id is not null
    group by
        trim(cast(department_id as varchar)),
        trim(cast(department_code as varchar)),
        trim(cast(functional_group as varchar))

),

hris_headcount as (

    select
        trim(cast(department_id as varchar)) as department_id,
        trim(cast(department_code as varchar)) as department_code,
        trim(cast(functional_group as varchar)) as functional_group,
        count(*) as hris_headcount_snapshot_rows
    from {{ ref('stg_hris__hr_headcount_snapshot') }}
    where department_id is not null
    group by
        trim(cast(department_id as varchar)),
        trim(cast(department_code as varchar)),
        trim(cast(functional_group as varchar))

),

workforce_compensation as (

    select
        trim(cast(department_id as varchar)) as department_id,
        count(*) as workforce_compensation_rows
    from {{ ref('stg_workforce__employee_compensation') }}
    where department_id is not null
    group by trim(cast(department_id as varchar))

),

workforce_headcount_plan as (

    select
        trim(cast(department_id as varchar)) as department_id,
        count(*) as workforce_headcount_plan_rows
    from {{ ref('stg_workforce__headcount_plan') }}
    where department_id is not null
    group by trim(cast(department_id as varchar))

),

workforce_payroll as (

    select
        trim(cast(department_id as varchar)) as department_id,
        count(*) as workforce_payroll_rows
    from {{ ref('stg_workforce__payroll_expense_lines') }}
    where department_id is not null
    group by trim(cast(department_id as varchar))

),

planning_budget as (

    select
        trim(cast(department_id as varchar)) as department_id,
        count(*) as planning_budget_rows
    from {{ ref('stg_planning__budget_lines') }}
    where department_id is not null
    group by trim(cast(department_id as varchar))

),

planning_forecast as (

    select
        trim(cast(department_id as varchar)) as department_id,
        count(*) as planning_forecast_rows
    from {{ ref('stg_planning__forecast_lines') }}
    where department_id is not null
    group by trim(cast(department_id as varchar))

),

planning_variance as (

    select
        trim(cast(department_id as varchar)) as department_id,
        count(*) as planning_variance_rows
    from {{ ref('stg_planning__variance_source_extract') }}
    where department_id is not null
    group by trim(cast(department_id as varchar))

),

department_universe as (

    select department_id from hris_employees
    union
    select department_id from hris_headcount
    union
    select department_id from workforce_compensation
    union
    select department_id from workforce_headcount_plan
    union
    select department_id from workforce_payroll
    union
    select department_id from planning_budget
    union
    select department_id from planning_forecast
    union
    select department_id from planning_variance

),

department_attributes as (

    select
        u.department_id,

        coalesce(e.department_code, h.department_code, u.department_id) as department_code,
        coalesce(e.functional_group, h.functional_group, 'Unknown') as functional_group,

        coalesce(e.hris_employee_rows, 0) as hris_employee_rows,
        coalesce(h.hris_headcount_snapshot_rows, 0) as hris_headcount_snapshot_rows,
        coalesce(wc.workforce_compensation_rows, 0) as workforce_compensation_rows,
        coalesce(whp.workforce_headcount_plan_rows, 0) as workforce_headcount_plan_rows,
        coalesce(wp.workforce_payroll_rows, 0) as workforce_payroll_rows,
        coalesce(pb.planning_budget_rows, 0) as planning_budget_rows,
        coalesce(pf.planning_forecast_rows, 0) as planning_forecast_rows,
        coalesce(pv.planning_variance_rows, 0) as planning_variance_rows

    from department_universe as u
    left join hris_employees as e
        on u.department_id = e.department_id
    left join hris_headcount as h
        on u.department_id = h.department_id
    left join workforce_compensation as wc
        on u.department_id = wc.department_id
    left join workforce_headcount_plan as whp
        on u.department_id = whp.department_id
    left join workforce_payroll as wp
        on u.department_id = wp.department_id
    left join planning_budget as pb
        on u.department_id = pb.department_id
    left join planning_forecast as pf
        on u.department_id = pf.department_id
    left join planning_variance as pv
        on u.department_id = pv.department_id

),

department_rows as (

    select
        md5(trim(upper(department_id))) as department_hk,

        department_id,
        department_code,

        case
            when department_id = 'DEPT_CS' then 'Customer Success'
            when department_id = 'DEPT_ENG' then 'Engineering'
            when department_id = 'DEPT_FINHR' then 'Finance & HR'
            when department_id = 'DEPT_GA' then 'General & Administrative'
            when department_id = 'DEPT_MARKETING' then 'Marketing'
            when department_id = 'DEPT_PRODUCT' then 'Product'
            when department_id = 'DEPT_SALES' then 'Sales'
            when department_id = 'DEPT_UNKNOWN' then 'Unknown / Legacy Operations'
            else department_code
        end as department_name,

        functional_group,

        case
            when functional_group in ('R&D', 'Product') then 'Product & Engineering'
            when functional_group in ('Sales', 'Marketing', 'Customer Success') then 'Go-to-Market'
            when functional_group in ('Finance & HR', 'G&A') then 'Corporate'
            when functional_group = 'Unknown' then 'Unknown'
            else 'Other'
        end as executive_function_group,

        case when department_id = 'DEPT_UNKNOWN' then true else false end as is_unknown_department,

        case when hris_employee_rows > 0 then true else false end as exists_in_hris_employees,
        case when hris_headcount_snapshot_rows > 0 then true else false end as exists_in_hris_headcount_snapshot,
        case when workforce_compensation_rows > 0 then true else false end as exists_in_workforce_compensation,
        case when workforce_headcount_plan_rows > 0 then true else false end as exists_in_workforce_headcount_plan,
        case when workforce_payroll_rows > 0 then true else false end as exists_in_workforce_payroll,
        case when planning_budget_rows > 0 then true else false end as exists_in_planning_budget,
        case when planning_forecast_rows > 0 then true else false end as exists_in_planning_forecast,
        case when planning_variance_rows > 0 then true else false end as exists_in_planning_variance,

        hris_employee_rows,
        hris_headcount_snapshot_rows,
        workforce_compensation_rows,
        workforce_headcount_plan_rows,
        workforce_payroll_rows,
        planning_budget_rows,
        planning_forecast_rows,
        planning_variance_rows,

        case
            when department_id = 'DEPT_SALES' then 10
            when department_id = 'DEPT_MARKETING' then 20
            when department_id = 'DEPT_CS' then 30
            when department_id = 'DEPT_PRODUCT' then 40
            when department_id = 'DEPT_ENG' then 50
            when department_id = 'DEPT_FINHR' then 60
            when department_id = 'DEPT_GA' then 70
            when department_id = 'DEPT_UNKNOWN' then 90
            else 99
        end as department_sort,

        false as is_unassigned

    from department_attributes

),

unassigned_row as (

    select
        md5('UNASSIGNED_DEPARTMENT') as department_hk,

        'UNASSIGNED' as department_id,
        'UNASSIGNED' as department_code,
        'Unassigned Department' as department_name,
        'Unassigned' as functional_group,
        'Unassigned' as executive_function_group,

        false as is_unknown_department,

        false as exists_in_hris_employees,
        false as exists_in_hris_headcount_snapshot,
        false as exists_in_workforce_compensation,
        false as exists_in_workforce_headcount_plan,
        false as exists_in_workforce_payroll,
        false as exists_in_planning_budget,
        false as exists_in_planning_forecast,
        false as exists_in_planning_variance,

        0 as hris_employee_rows,
        0 as hris_headcount_snapshot_rows,
        0 as workforce_compensation_rows,
        0 as workforce_headcount_plan_rows,
        0 as workforce_payroll_rows,
        0 as planning_budget_rows,
        0 as planning_forecast_rows,
        0 as planning_variance_rows,

        -1 as department_sort,

        true as is_unassigned

)

select *
from unassigned_row

union all

select *
from department_rows
