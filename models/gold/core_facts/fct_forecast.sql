{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'core_fact', 'forecast']
) }}

with source as (

    select
        forecast_line_pk,
        forecast_line_id,
        forecast_version_code,
        scenario_type,
        fiscal_year,
        posting_period,
        period_start_date,
        period_end_date,
        department_id,
        account_code,
        account_name,
        account_class,
        financial_statement,
        currency,
        forecast_amount_local,
        forecast_amount_gbp,
        source_budget_amount_local,
        source_budget_amount_gbp,
        forecast_basis,
        planning_driver,
        driver_quantity,
        driver_rate,
        scenario_multiplier,
        forecast_method,
        source_budget_version_code,
        source_budget_line_id,
        is_locked,
        source_system,
        is_system_generated,
        is_defect,
        defect_type,
        created_date,
        updated_date,
        _atlas_row_hash,
        _atlas_ingested_at,
        _atlas_source_file
    from {{ ref('stg_planning__forecast_lines') }}

),

renamed as (

    select
        md5(trim(upper(cast(forecast_line_id as varchar)))) as forecast_line_hk,

        forecast_line_pk,
        forecast_line_id,

        case
            when posting_period is not null
            then md5(strftime(posting_period, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as forecast_date_hk,

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
            when forecast_version_code is not null and trim(cast(forecast_version_code as varchar)) <> ''
             and scenario_type is not null and trim(cast(scenario_type as varchar)) <> ''
            then md5(
                trim(upper(cast(forecast_version_code as varchar)))
                || '|'
                || trim(upper(cast(scenario_type as varchar)))
            )
            else md5('UNASSIGNED')
        end as forecast_scenario_hk,

        case
            when source_budget_version_code is not null and trim(cast(source_budget_version_code as varchar)) <> ''
            then md5(trim(upper(cast(source_budget_version_code as varchar))))
            else md5('UNASSIGNED')
        end as source_budget_version_hk,

        nullif(trim(upper(cast(forecast_version_code as varchar))), '') as forecast_version_code,
        coalesce(nullif(trim(cast(scenario_type as varchar)), ''), 'Unknown') as forecast_scenario,

        fiscal_year,
        posting_period,
        period_start_date,
        period_end_date,

        nullif(trim(upper(cast(department_id as varchar))), '') as department_id,
        nullif(trim(cast(account_code as varchar)), '') as account_code,
        account_name,
        account_class,
        financial_statement,

        coalesce(nullif(trim(upper(cast(currency as varchar))), ''), 'UNKNOWN') as currency_code,

        coalesce(forecast_amount_local, 0) as forecast_amount_local,
        coalesce(forecast_amount_gbp, 0) as forecast_amount_gbp,
        coalesce(source_budget_amount_local, 0) as source_budget_amount_local,
        coalesce(source_budget_amount_gbp, 0) as source_budget_amount_gbp,

        coalesce(forecast_amount_local, 0) - coalesce(source_budget_amount_local, 0) as forecast_vs_source_budget_variance_local,
        coalesce(forecast_amount_gbp, 0) - coalesce(source_budget_amount_gbp, 0) as forecast_vs_source_budget_variance_gbp,

        forecast_basis,
        planning_driver,
        coalesce(driver_quantity, 0) as driver_quantity,
        coalesce(driver_rate, 0) as driver_rate,
        coalesce(scenario_multiplier, 1) as scenario_multiplier,
        forecast_method,

        nullif(trim(upper(cast(source_budget_version_code as varchar))), '') as source_budget_version_code,
        nullif(trim(cast(source_budget_line_id as varchar)), '') as source_budget_line_id,

        coalesce(is_locked, false) as is_locked,
        source_system,
        coalesce(is_system_generated, false) as is_system_generated,
        coalesce(is_defect, false) as is_defect,
        nullif(trim(cast(defect_type as varchar)), '') as defect_type,

        case when source_budget_line_id is not null and trim(cast(source_budget_line_id as varchar)) <> '' then true else false end as has_source_budget_line,
        case when forecast_basis = 'ACTUAL_FS_ALLOCATED_TO_AOP_GRAIN' then true else false end as is_actual_fs_allocated_basis,
        case when forecast_basis = 'ACTUAL_WORKFORCE_SUBLEDGER' then true else false end as is_actual_workforce_subledger_basis,
        case when forecast_basis = 'SCENARIO_DRIVER_FORECAST' then true else false end as is_scenario_driver_forecast_basis,

        created_date,
        updated_date,

        _atlas_row_hash,
        _atlas_ingested_at,
        _atlas_source_file

    from source

)

select *
from renamed
