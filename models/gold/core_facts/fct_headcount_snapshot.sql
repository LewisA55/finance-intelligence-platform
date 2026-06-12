{{ config(
    materialized = 'table',
    schema = 'gold'
) }}

with source as (

    select *
    from {{ ref('stg_hris__hr_headcount_snapshot') }}

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
        date_day
    from {{ ref('dim_date') }}

),

final as (

    select
        -- Primary key
        md5(
            coalesce(cast(source.employee_id as varchar), 'UNASSIGNED')
            || '|' ||
            coalesce(cast(source.snapshot_month as varchar), 'UNASSIGNED')
        ) as headcount_snapshot_hk,

        -- Conformed dimension keys
        coalesce(dim_employee.employee_hk, md5('UNASSIGNED')) as employee_hk,
        coalesce(dim_department.department_hk, md5('UNASSIGNED')) as department_hk,
        coalesce(dim_region.region_hk, md5('UNASSIGNED')) as region_hk,
        coalesce(snapshot_date.date_hk, md5('UNASSIGNED')) as snapshot_month_date_hk,

        -- Natural keys / degenerate dimensions
        source.employee_id,
        source.department_id,
        source.department_code,
        source.functional_group,
        source.region_id,
        source.currency_code,
        source.job_level,
        source.employment_status,

        -- Snapshot date
        source.snapshot_month as snapshot_month_date,

        -- Measures
        source.monthly_salary_local,
        source.monthly_salary_gbp,
        source.fte_count,
        case when source.is_active then source.fte_count else 0 end as active_fte_count,
        case when source.is_ghost_headcount then source.fte_count else 0 end as ghost_fte_count,
        case when source.is_active then 1 else 0 end as active_headcount_count,
        case when source.is_ghost_headcount then 1 else 0 end as ghost_headcount_count,

        -- Source status flags
        source.is_active,
        source.is_ghost_headcount,

        -- Gold semantic flags
        source.is_active as is_active_headcount,
        not source.is_active as is_inactive_headcount,
        source.department_id = 'DEPT_UNKNOWN' as is_unknown_department,
        lower(trim(source.employment_status)) = 'terminated' as is_terminated_status,
        lower(trim(source.employment_status)) = 'active' as is_active_status,
        (
            (lower(trim(source.employment_status)) = 'terminated' and source.is_active)
            or
            (lower(trim(source.employment_status)) = 'active' and not source.is_active)
        ) as is_status_active_mismatch,
        source.snapshot_month = last_day(source.snapshot_month) as is_month_end_snapshot,

        -- Atlas lineage
        source._atlas_row_hash,
        source._atlas_ingested_at,
        source._atlas_source_file

    from source

    left join dim_employee
        on source.employee_id = dim_employee.employee_id

    left join dim_department
        on source.department_id = dim_department.department_id

    left join dim_region
        on source.region_id = dim_region.region_id

    left join dim_date as snapshot_date
        on source.snapshot_month = snapshot_date.date_day

)

select *
from final
