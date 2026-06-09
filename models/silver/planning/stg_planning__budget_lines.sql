{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'planning', 'budget_lines']
) }}

with source as (

    select *
    from {{ source('bronze', 'planning__budget_lines') }}

),

renamed_and_casted as (

    select
        trim(cast(budget_line_pk as varchar)) as budget_line_pk,
        trim(cast(budget_line_id as varchar)) as budget_line_id,

        trim(cast(budget_version_code as varchar)) as budget_version_code,
        cast(fiscal_year as integer) as fiscal_year,

        strptime(trim(cast(posting_period as varchar)) || '-01', '%Y-%m-%d')::date as posting_period,
        {{ safecast_date('period_start_date') }} as period_start_date,
        {{ safecast_date('period_end_date') }} as period_end_date,

        trim(cast(department_id as varchar)) as department_id,

        trim(cast(account_code as varchar)) as account_code,
        trim(cast(account_name as varchar)) as account_name,
        trim(cast(account_class as varchar)) as account_class,
        trim(cast(financial_statement as varchar)) as financial_statement,

        upper(trim(cast(currency as varchar))) as currency,

        {{ safecast_decimal('budget_amount_local') }} as budget_amount_local,
        {{ safecast_decimal('budget_amount_gbp') }} as budget_amount_gbp,

        trim(cast(planning_driver as varchar)) as planning_driver,
        {{ safecast_decimal('driver_quantity') }} as driver_quantity,
        {{ safecast_decimal('driver_rate') }} as driver_rate,

        trim(cast(budget_method as varchar)) as budget_method,

        {{ safecast_boolean('is_locked_flag') }} as is_locked,
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
