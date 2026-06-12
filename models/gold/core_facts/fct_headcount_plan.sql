{{ config(
    materialized = 'table',
    schema = 'gold'
) }}

with source as (

    select *
    from {{ ref('stg_workforce__headcount_plan') }}

),

dim_employee as (

    select
        employee_hk,
        employee_id
    from {{ ref('dim_employee') }}

),

dim_department as (

    select
        department_hk,
        department_id
    from {{ ref('dim_department') }}

),

dim_region as (

    select
        region_hk,
        region_id
    from {{ ref('dim_region') }}

),

dim_date as (

    select
        date_hk,
        date_day,
        is_unassigned
    from {{ ref('dim_date') }}

),

unassigned_date as (

    select
        date_hk as unassigned_date_hk
    from dim_date
    where is_unassigned = true

),

final as (

    select
        -- Primary key
        source.position_pk as headcount_plan_hk,
        source.position_id,

        -- Conformed dimension keys
        coalesce(dim_employee.employee_hk, md5('UNASSIGNED')) as employee_hk,
        coalesce(dim_department.department_hk, md5('UNASSIGNED')) as department_hk,
        coalesce(dim_region.region_hk, md5('UNASSIGNED')) as region_hk,
        coalesce(planned_hire_date.date_hk, unassigned_date.unassigned_date_hk) as planned_hire_date_hk,
        coalesce(planned_start_period.date_hk, unassigned_date.unassigned_date_hk) as planned_start_period_date_hk,

        -- Natural keys / degenerate dimensions
        source.employee_id,
        source.plan_status,
        source.department_id,
        source.region_id,
        source.country_code,
        source.currency as currency_code,
        source.role_family,
        source.seniority_level,

        -- Planning dates
        source.planned_hire_date,
        source.planned_start_period,

        -- Measures / planning assumptions
        source.target_salary_low_local,
        source.target_salary_mid_local,
        source.target_salary_high_local,
        source.target_salary_mid_gbp,
        source.fx_rate_to_gbp,
        1 as planned_position_count,

        -- Lifecycle flags
        source.plan_status = 'ACTIVE' as is_active_position,
        source.plan_status = 'OPEN_BUDGETED' as is_open_budgeted_position,
        source.plan_status = 'BACKFILL' as is_backfill_position,
        source.plan_status in ('OPEN_BUDGETED', 'BACKFILL') as is_open_position,
        source.plan_status = 'ACTIVE'
            and source.employee_id is not null
            and trim(source.employee_id) <> '' as is_filled_position,
        source.is_backfill,
        not source.is_backfill as is_growth_position,

        -- Date completeness / planning telemetry
        source.planned_hire_date is null as is_planned_hire_date_missing,
        source.planned_start_period is null as is_planned_start_period_missing,
        source.planned_hire_date is not null
            and source.planned_hire_date < current_date as is_planned_hire_date_in_past,

        -- Control / exception flags
        source.department_id = 'DEPT_UNKNOWN' as is_unknown_department,
        source.is_defect,
        source.defect_type,

        -- Source context
        source.source_system,
        source.is_system_generated,
        source.created_date,
        source.updated_date,

        -- Atlas lineage
        source._atlas_row_hash,
        source._atlas_ingested_at,
        source._atlas_source_file

    from source

    cross join unassigned_date

    left join dim_employee
        on source.employee_id = dim_employee.employee_id

    left join dim_department
        on source.department_id = dim_department.department_id

    left join dim_region
        on source.region_id = dim_region.region_id

    left join dim_date as planned_hire_date
        on source.planned_hire_date = planned_hire_date.date_day

    left join dim_date as planned_start_period
        on source.planned_start_period = planned_start_period.date_day

)

select *
from final
