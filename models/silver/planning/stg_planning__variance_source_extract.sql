{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'planning', 'variance_source']
) }}

with source as (

    select *
    from {{ source('bronze', 'planning__variance_source_extract') }}

),

renamed_and_casted as (

    select
        trim(cast(variance_extract_pk as varchar)) as variance_extract_pk,
        trim(cast(variance_extract_line_id as varchar)) as variance_extract_line_id,

        trim(cast(forecast_version_code as varchar)) as forecast_version_code,
        trim(cast(forecast_scenario as varchar)) as forecast_scenario,
        trim(cast(budget_version_code as varchar)) as budget_version_code,

        cast(fiscal_year as integer) as fiscal_year,

        strptime(trim(cast(posting_period as varchar)) || '-01', '%Y-%m-%d')::date as posting_period,
        {{ safecast_date('period_start_date') }} as period_start_date,
        {{ safecast_date('period_end_date') }} as period_end_date,

        trim(cast(period_status as varchar)) as period_status,

        trim(cast(department_id as varchar)) as department_id,

        trim(cast(account_code as varchar)) as account_code,
        trim(cast(account_name as varchar)) as account_name,
        trim(cast(account_class as varchar)) as account_class,
        trim(cast(financial_statement as varchar)) as financial_statement,

        upper(trim(cast(currency as varchar))) as currency,

        trim(cast(planning_driver as varchar)) as planning_driver,
        trim(cast(forecast_basis as varchar)) as forecast_basis,

        {{ safecast_decimal('actual_amount_local') }} as actual_amount_local,
        {{ safecast_decimal('actual_amount_gbp') }} as actual_amount_gbp,
        {{ safecast_decimal('budget_amount_local') }} as budget_amount_local,
        {{ safecast_decimal('budget_amount_gbp') }} as budget_amount_gbp,
        {{ safecast_decimal('forecast_amount_local') }} as forecast_amount_local,
        {{ safecast_decimal('forecast_amount_gbp') }} as forecast_amount_gbp,

        {{ safecast_decimal('actual_vs_budget_variance_gbp') }} as actual_vs_budget_variance_gbp,
        {{ safecast_decimal('actual_vs_budget_variance_pct') }} as actual_vs_budget_variance_pct,
        trim(cast(actual_vs_budget_favourability as varchar)) as actual_vs_budget_favourability,

        {{ safecast_decimal('actual_vs_forecast_variance_gbp') }} as actual_vs_forecast_variance_gbp,
        {{ safecast_decimal('actual_vs_forecast_variance_pct') }} as actual_vs_forecast_variance_pct,
        trim(cast(actual_vs_forecast_favourability as varchar)) as actual_vs_forecast_favourability,

        {{ safecast_decimal('forecast_vs_budget_variance_gbp') }} as forecast_vs_budget_variance_gbp,
        {{ safecast_decimal('forecast_vs_budget_variance_pct') }} as forecast_vs_budget_variance_pct,
        trim(cast(forecast_vs_budget_favourability as varchar)) as forecast_vs_budget_favourability,

        trim(cast(variance_category as varchar)) as variance_category,
        trim(cast(variance_driver_group as varchar)) as variance_driver_group,

        {{ safecast_boolean('is_actual_period') }} as is_actual_period,
        {{ safecast_boolean('is_forecast_period') }} as is_forecast_period,

        trim(cast(source_budget_line_id as varchar)) as source_budget_line_id,
        trim(cast(source_forecast_line_id as varchar)) as source_forecast_line_id,

        trim(cast(actual_source_basis as varchar)) as actual_source_basis,

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
