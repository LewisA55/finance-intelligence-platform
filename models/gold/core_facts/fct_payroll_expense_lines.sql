{{ config(
    materialized = 'table',
    schema = 'gold'
) }}

with source as (

    select *
    from {{ ref('stg_workforce__payroll_expense_lines') }}

),

dim_department as (

    select
        department_hk,
        department_id
    from {{ ref('dim_department') }}

),

dim_gl_account as (

    select
        gl_account_hk,
        account_code,
        account_class,
        account_name
    from {{ ref('dim_gl_account') }}

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
        source.payroll_expense_pk as payroll_expense_hk,
        source.payroll_expense_line_id,

        -- Conformed dimension keys
        coalesce(dim_department.department_hk, md5('UNASSIGNED')) as department_hk,
        coalesce(dim_gl_account.gl_account_hk, md5('UNASSIGNED_GL_ACCOUNT')) as gl_account_hk,
        coalesce(payroll_expense_period_date.date_hk, md5('UNASSIGNED')) as payroll_expense_period_date_hk,
        coalesce(period_start_date.date_hk, md5('UNASSIGNED')) as period_start_date_hk,
        coalesce(period_end_date.date_hk, md5('UNASSIGNED')) as period_end_date_hk,

        -- Natural keys / degenerate dimensions
        source.department_id,
        source.account_code,
        source.account_name,
        source.currency as currency_code,
        source.cost_component,

        -- Dates
        source.posting_period as payroll_expense_period_date,
        source.period_start_date,
        source.period_end_date,

        -- Measures
        source.employee_count,
        source.debit_local,
        source.credit_local,
        source.debit_gbp,
        source.credit_gbp,
        source.net_amount_local,
        source.net_amount_gbp,
        abs(source.net_amount_gbp) as absolute_net_amount_gbp,

        -- Component flags
        source.cost_component = 'BASE_SALARY' as is_base_salary,
        source.cost_component = 'EMPLOYER_TAX' as is_employer_tax,
        source.cost_component = 'BENEFITS' as is_benefits,
        source.cost_component = 'BONUS_ACCRUAL' as is_bonus_accrual,
        source.cost_component in (
            'BASE_SALARY',
            'EMPLOYER_TAX',
            'BENEFITS',
            'BONUS_ACCRUAL'
        ) as is_payroll_related_cost,

        -- Payroll accounting flags
        source.account_code = '6100' as is_payroll_expense_account,
        dim_gl_account.account_class = 'Expense' as is_expense_account,
        source.credit_gbp = 0 and source.credit_local = 0 as is_zero_credit_line,
        source.net_amount_gbp > 0 as is_positive_net_expense,

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

    left join dim_department
        on source.department_id = dim_department.department_id

    left join dim_gl_account
        on source.account_code = dim_gl_account.account_code

    left join dim_date as payroll_expense_period_date
        on source.posting_period = payroll_expense_period_date.date_day

    left join dim_date as period_start_date
        on source.period_start_date = period_start_date.date_day

    left join dim_date as period_end_date
        on source.period_end_date = period_end_date.date_day

)

select *
from final
