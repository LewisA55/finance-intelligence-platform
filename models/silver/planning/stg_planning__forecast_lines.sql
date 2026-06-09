{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'planning', 'forecast_lines']
) }}

with source as (

    select *
    from {{ source('bronze', 'planning__forecast_lines') }}

),

renamed_and_casted as (

    select
        trim(cast(forecast_line_pk as varchar)) as forecast_line_pk,
        trim(cast(forecast_line_id as varchar)) as forecast_line_id,

        trim(cast(forecast_version_code as varchar)) as forecast_version_code,
        trim(cast(scenario_type as varchar)) as scenario_type,

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

        {{ safecast_decimal('forecast_amount_local') }} as forecast_amount_local,
        {{ safecast_decimal('forecast_amount_gbp') }} as forecast_amount_gbp,
        {{ safecast_decimal('source_budget_amount_local') }} as source_budget_amount_local,
        {{ safecast_decimal('source_budget_amount_gbp') }} as source_budget_amount_gbp,

        trim(cast(forecast_basis as varchar)) as forecast_basis,
        trim(cast(planning_driver as varchar)) as planning_driver,

        {{ safecast_decimal('driver_quantity') }} as driver_quantity,
        {{ safecast_decimal('driver_rate') }} as driver_rate,
        {{ safecast_decimal('scenario_multiplier') }} as scenario_multiplier,

        trim(cast(forecast_method as varchar)) as forecast_method,

        trim(cast(source_budget_version_code as varchar)) as source_budget_version_code,
        trim(cast(source_budget_line_id as varchar)) as source_budget_line_id,

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
