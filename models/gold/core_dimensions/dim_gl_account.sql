{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'core_dimension', 'gl_account']
) }}

with source as (

    select *
    from {{ ref('stg_accounting__chart_of_accounts') }}

),

account_rows as (

    select
        md5(coalesce(trim(upper(account_code)), 'UNASSIGNED_GL_ACCOUNT')) as gl_account_hk,

        account_pk,
        trim(cast(account_code as varchar)) as account_code,
        try_cast(account_code as integer) as account_code_number,
        trim(cast(account_name as varchar)) as account_name,

        trim(cast(account_class as varchar)) as account_class,
        trim(cast(account_type as varchar)) as account_type,
        trim(cast(financial_statement as varchar)) as financial_statement,
        trim(cast(report_group as varchar)) as report_group,
        trim(cast(report_subgroup as varchar)) as report_subgroup,
        trim(cast(normal_balance as varchar)) as normal_balance,

        is_pnl,
        is_balance_sheet,
        is_cash_account,
        is_control_account,
        is_active,

        case when account_class = 'Revenue' then true else false end as is_revenue_account,
        case when account_class = 'Expense' then true else false end as is_expense_account,
        case when account_class = 'Asset' then true else false end as is_asset_account,
        case when account_class = 'Liability' then true else false end as is_liability_account,
        case when account_class = 'Equity' then true else false end as is_equity_account,

        case when financial_statement = 'Income Statement' then true else false end as is_income_statement_account,
        case when financial_statement = 'Balance Sheet' then true else false end as is_balance_sheet_account,

        case
            when account_class = 'Revenue' then 1
            when account_class = 'Expense' then 2
            when account_class = 'Asset' then 3
            when account_class = 'Liability' then 4
            when account_class = 'Equity' then 5
            else 99
        end as account_class_sort,

        case
            when financial_statement = 'Income Statement' then 1
            when financial_statement = 'Balance Sheet' then 2
            else 99
        end as financial_statement_sort,

        created_date,
        updated_date,

        _atlas_row_hash,
        _atlas_ingested_at,
        _atlas_source_file,

        false as is_unassigned

    from source

),

unassigned_row as (

    select
        md5('UNASSIGNED_GL_ACCOUNT') as gl_account_hk,

        'UNASSIGNED_GL_ACCOUNT' as account_pk,
        'UNASSIGNED' as account_code,
        -1 as account_code_number,
        'Unassigned GL Account' as account_name,

        'Unassigned' as account_class,
        'Unassigned' as account_type,
        'Unassigned' as financial_statement,
        'Unassigned' as report_group,
        'Unassigned' as report_subgroup,
        'Unassigned' as normal_balance,

        false as is_pnl,
        false as is_balance_sheet,
        false as is_cash_account,
        false as is_control_account,
        false as is_active,

        false as is_revenue_account,
        false as is_expense_account,
        false as is_asset_account,
        false as is_liability_account,
        false as is_equity_account,

        false as is_income_statement_account,
        false as is_balance_sheet_account,

        -1 as account_class_sort,
        -1 as financial_statement_sort,

        cast(null as date) as created_date,
        cast(null as date) as updated_date,

        cast(null as varchar) as _atlas_row_hash,
        cast(null as timestamp) as _atlas_ingested_at,
        cast(null as varchar) as _atlas_source_file,

        true as is_unassigned

)

select *
from unassigned_row

union all

select *
from account_rows
