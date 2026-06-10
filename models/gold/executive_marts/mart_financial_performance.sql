{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'executive_mart', 'financial_performance']
) }}

with source as (

    select
        variance_extract_pk,
        variance_extract_line_id,

        forecast_version_code,
        forecast_scenario,
        budget_version_code,

        fiscal_year,
        posting_period,
        period_start_date,
        period_end_date,
        period_status,

        department_id,
        account_code,
        account_name,
        account_class,
        financial_statement,
        currency,

        planning_driver,
        forecast_basis,

        actual_amount_local,
        actual_amount_gbp,
        budget_amount_local,
        budget_amount_gbp,
        forecast_amount_local,
        forecast_amount_gbp,

        actual_vs_budget_variance_gbp,
        actual_vs_budget_variance_pct,
        actual_vs_budget_favourability,

        actual_vs_forecast_variance_gbp,
        actual_vs_forecast_variance_pct,
        actual_vs_forecast_favourability,

        forecast_vs_budget_variance_gbp,
        forecast_vs_budget_variance_pct,
        forecast_vs_budget_favourability,

        variance_category,
        variance_driver_group,

        is_actual_period,
        is_forecast_period,

        source_budget_line_id,
        source_forecast_line_id,
        actual_source_basis,

        source_system,
        is_system_generated,
        is_defect,
        defect_type,
        created_date,
        updated_date,

        _atlas_row_hash,
        _atlas_ingested_at,
        _atlas_source_file

    from {{ ref('stg_planning__variance_source_extract') }}

),

renamed as (

    select
        md5(trim(upper(cast(variance_extract_line_id as varchar)))) as financial_performance_hk,

        variance_extract_pk,
        variance_extract_line_id,

        case
            when posting_period is not null
            then md5(strftime(posting_period, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as performance_date_hk,

        case
            when account_code is not null and trim(cast(account_code as varchar)) <> ''
            then md5(trim(upper(cast(account_code as varchar))))
            else md5('UNASSIGNED')
        end as gl_account_hk,

        case
            when department_id is not null and trim(cast(department_id as varchar)) <> ''
            then md5(trim(upper(cast(department_id as varchar))))
            else md5('UNASSIGNED')
        end as department_hk,

        case
            when budget_version_code is not null and trim(cast(budget_version_code as varchar)) <> ''
            then md5(trim(upper(cast(budget_version_code as varchar))))
            else md5('UNASSIGNED')
        end as budget_version_hk,

        case
            when forecast_version_code is not null and trim(cast(forecast_version_code as varchar)) <> ''
             and forecast_scenario is not null and trim(cast(forecast_scenario as varchar)) <> ''
            then md5(
                trim(upper(cast(forecast_version_code as varchar)))
                || '|'
                || trim(upper(cast(forecast_scenario as varchar)))
            )
            else md5('UNASSIGNED')
        end as forecast_scenario_hk,

        nullif(trim(upper(cast(forecast_version_code as varchar))), '') as forecast_version_code,
        coalesce(nullif(trim(cast(forecast_scenario as varchar)), ''), 'Unknown') as forecast_scenario,
        nullif(trim(upper(cast(budget_version_code as varchar))), '') as budget_version_code,

        fiscal_year,
        posting_period,
        period_start_date,
        period_end_date,
        coalesce(nullif(trim(cast(period_status as varchar)), ''), 'Unknown') as period_status,

        nullif(trim(upper(cast(department_id as varchar))), '') as department_id,
        nullif(trim(cast(account_code as varchar)), '') as account_code,
        account_name,
        account_class,
        financial_statement,
        coalesce(nullif(trim(upper(cast(currency as varchar))), ''), 'UNKNOWN') as currency_code,

        planning_driver,
        forecast_basis,

        actual_amount_local,
        actual_amount_gbp,
        budget_amount_local,
        budget_amount_gbp,
        forecast_amount_local,
        forecast_amount_gbp,

        actual_vs_budget_variance_gbp,
        actual_vs_budget_variance_pct,
        actual_vs_budget_favourability,

        actual_vs_forecast_variance_gbp,
        actual_vs_forecast_variance_pct,
        actual_vs_forecast_favourability,

        forecast_vs_budget_variance_gbp,
        forecast_vs_budget_variance_pct,
        forecast_vs_budget_favourability,

        variance_category,
        variance_driver_group,

        coalesce(is_actual_period, false) as is_actual_period,
        coalesce(is_forecast_period, false) as is_forecast_period,

        case when period_status = 'Actual' then true else false end as is_actual_period_status,
        case when period_status = 'Forecast' then true else false end as is_forecast_period_status,

        nullif(trim(cast(source_budget_line_id as varchar)), '') as source_budget_line_id,
        nullif(trim(cast(source_forecast_line_id as varchar)), '') as source_forecast_line_id,
        actual_source_basis,

        case when source_budget_line_id is not null and trim(cast(source_budget_line_id as varchar)) <> '' then true else false end as has_source_budget_line,
        case when source_forecast_line_id is not null and trim(cast(source_forecast_line_id as varchar)) <> '' then true else false end as has_source_forecast_line,

        case when actual_amount_gbp is not null then true else false end as has_actual_amount,
        case when budget_amount_gbp is not null then true else false end as has_budget_amount,
        case when forecast_amount_gbp is not null then true else false end as has_forecast_amount,

        source_system,
        coalesce(is_system_generated, false) as is_system_generated,
        coalesce(is_defect, false) as is_defect,
        nullif(trim(cast(defect_type as varchar)), '') as defect_type,
        created_date,
        updated_date,

        _atlas_row_hash,
        _atlas_ingested_at,
        _atlas_source_file

    from source

)

select *
from renamed
