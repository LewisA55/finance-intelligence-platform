{{ config(
    materialized = 'table',
    schema = 'gold'
) }}

with source as (

    select *
    from {{ ref('stg_workforce__employee_compensation') }}

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
        source.compensation_pk as employee_compensation_hk,
        source.compensation_line_id,

        -- Conformed dimension keys
        coalesce(dim_employee.employee_hk, md5('UNASSIGNED')) as employee_hk,
        coalesce(dim_department.department_hk, md5('UNASSIGNED')) as department_hk,
        coalesce(dim_region.region_hk, md5('UNASSIGNED')) as region_hk,
        coalesce(compensation_period_date.date_hk, md5('UNASSIGNED')) as compensation_period_date_hk,
        coalesce(period_start_date.date_hk, md5('UNASSIGNED')) as period_start_date_hk,
        coalesce(period_end_date.date_hk, md5('UNASSIGNED')) as period_end_date_hk,

        -- Natural keys / degenerate dimensions
        source.employee_id,
        source.department_id,
        source.region_id,
        source.country_code,
        source.currency as currency_code,
        source.compensation_component,

        -- Dates
        source.posting_period as compensation_period_date,
        source.period_start_date,
        source.period_end_date,

        -- Measures
        source.annual_base_salary_local,
        source.monthly_base_salary_local,
        source.component_rate,
        source.amount_local,
        source.amount_gbp,
        source.fx_rate_to_gbp,

        -- Component flags
        source.compensation_component = 'BASE_SALARY' as is_base_salary,
        source.compensation_component = 'EMPLOYER_TAX' as is_employer_tax,
        source.compensation_component = 'BENEFITS' as is_benefits,
        source.compensation_component = 'BONUS_ACCRUAL' as is_bonus_accrual,
        source.compensation_component in (
            'BASE_SALARY',
            'EMPLOYER_TAX',
            'BENEFITS',
            'BONUS_ACCRUAL'
        ) as is_payroll_related_cost,

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

    left join dim_employee
        on source.employee_id = dim_employee.employee_id

    left join dim_department
        on source.department_id = dim_department.department_id

    left join dim_region
        on source.region_id = dim_region.region_id

    left join dim_date as compensation_period_date
        on source.posting_period = compensation_period_date.date_day

    left join dim_date as period_start_date
        on source.period_start_date = period_start_date.date_day

    left join dim_date as period_end_date
        on source.period_end_date = period_end_date.date_day

)

select *
from final
