{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'workforce', 'payroll_actuals']
) }}

with source as (

    select *
    from {{ source('bronze', 'workforce__payroll_expense_lines') }}

),

renamed_and_casted as (

    select
        trim(cast(payroll_expense_pk as varchar)) as payroll_expense_pk,
        trim(cast(payroll_expense_line_id as varchar)) as payroll_expense_line_id,

        cast(date_trunc('month', {{ safecast_date('period_start_date') }}) as date) as posting_period,
        {{ safecast_date('period_start_date') }} as period_start_date,
        {{ safecast_date('period_end_date') }} as period_end_date,

        trim(cast(department_id as varchar)) as department_id,

        trim(cast(account_code as varchar)) as account_code,
        trim(cast(account_name as varchar)) as account_name,

        upper(trim(cast(currency as varchar))) as currency,
        trim(cast(cost_component as varchar)) as cost_component,

        {{ safecast_decimal('employee_count') }} as employee_count,

        {{ safecast_decimal('debit_local') }} as debit_local,
        {{ safecast_decimal('credit_local') }} as credit_local,
        {{ safecast_decimal('debit_gbp') }} as debit_gbp,
        {{ safecast_decimal('credit_gbp') }} as credit_gbp,

        {{ safecast_decimal('debit_local') }} - {{ safecast_decimal('credit_local') }} as net_amount_local,
        {{ safecast_decimal('debit_gbp') }} - {{ safecast_decimal('credit_gbp') }} as net_amount_gbp,

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
