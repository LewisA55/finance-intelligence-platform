{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'core_dimension', 'forecast_scenario']
) }}

with forecast_source as (

    select
        trim(upper(cast(forecast_version_code as varchar))) as forecast_version_code,
        coalesce(nullif(trim(cast(scenario_type as varchar)), ''), 'Unknown') as forecast_scenario,
        trim(upper(cast(forecast_version_code as varchar))) || '|' || coalesce(nullif(trim(upper(cast(scenario_type as varchar))), ''), 'UNKNOWN') as forecast_scenario_nk,

        min(fiscal_year) as fiscal_year,
        min(period_start_date) as forecast_start_period,
        max(period_end_date) as forecast_end_period,
        min(coalesce(nullif(trim(upper(cast(source_budget_version_code as varchar))), ''), 'UNASSIGNED')) as source_budget_version_code,
        count(*) as forecast_line_rows,
        count(distinct forecast_basis) as distinct_forecast_basis_count,
        min(case when is_locked then 1 else 0 end) = 1 as is_locked,
        min(created_date) as created_date,
        max(updated_date) as updated_date

    from {{ ref('stg_planning__forecast_lines') }}
    where forecast_version_code is not null
      and trim(forecast_version_code) <> ''
    group by
        trim(upper(cast(forecast_version_code as varchar))),
        coalesce(nullif(trim(cast(scenario_type as varchar)), ''), 'Unknown'),
        trim(upper(cast(forecast_version_code as varchar))) || '|' || coalesce(nullif(trim(upper(cast(scenario_type as varchar))), ''), 'UNKNOWN')

),

forecast_basis_summary as (

    select
        trim(upper(cast(forecast_version_code as varchar))) || '|' || coalesce(nullif(trim(upper(cast(scenario_type as varchar))), ''), 'UNKNOWN') as forecast_scenario_nk,

        sum(case when forecast_basis = 'ACTUAL_FS_ALLOCATED_TO_AOP_GRAIN' then 1 else 0 end) as actual_fs_allocated_rows,
        sum(case when forecast_basis = 'ACTUAL_WORKFORCE_SUBLEDGER' then 1 else 0 end) as actual_workforce_subledger_rows,
        sum(case when forecast_basis = 'SCENARIO_DRIVER_FORECAST' then 1 else 0 end) as scenario_driver_forecast_rows

    from {{ ref('stg_planning__forecast_lines') }}
    where forecast_version_code is not null
      and trim(forecast_version_code) <> ''
    group by
        trim(upper(cast(forecast_version_code as varchar))) || '|' || coalesce(nullif(trim(upper(cast(scenario_type as varchar))), ''), 'UNKNOWN')

),

variance_extract as (

    select
        trim(upper(cast(forecast_version_code as varchar))) || '|' || coalesce(nullif(trim(upper(cast(forecast_scenario as varchar))), ''), 'UNKNOWN') as forecast_scenario_nk,

        count(*) as variance_extract_rows,
        sum(case when period_status = 'Actual' then 1 else 0 end) as actual_period_variance_rows,
        sum(case when period_status = 'Forecast' then 1 else 0 end) as forecast_period_variance_rows

    from {{ ref('stg_planning__variance_source_extract') }}
    where forecast_version_code is not null
      and trim(forecast_version_code) <> ''
    group by
        trim(upper(cast(forecast_version_code as varchar))) || '|' || coalesce(nullif(trim(upper(cast(forecast_scenario as varchar))), ''), 'UNKNOWN')

),

forecast_rows as (

    select
        md5(f.forecast_scenario_nk) as forecast_scenario_hk,

        f.forecast_scenario_nk,
        f.forecast_version_code,
        f.forecast_scenario,

        case
            when f.forecast_scenario = 'Base Case' then 'Base Case'
            when f.forecast_scenario = 'Upside Case' then 'Upside Case'
            when f.forecast_scenario = 'Downside Case' then 'Downside Case'
            else 'Other'
        end as scenario_type,

        f.fiscal_year,
        f.forecast_start_period,
        f.forecast_end_period,

        f.source_budget_version_code,
        md5(f.source_budget_version_code) as source_budget_version_hk,

        false as is_actuals,

        case when f.forecast_scenario = 'Base Case' then true else false end as is_base_case,
        case when f.forecast_scenario = 'Upside Case' then true else false end as is_upside_case,
        case when f.forecast_scenario = 'Downside Case' then true else false end as is_downside_case,

        f.is_locked,

        case when coalesce(f.forecast_line_rows, 0) > 0 then true else false end as exists_in_forecast_lines,
        case when coalesce(v.variance_extract_rows, 0) > 0 then true else false end as exists_in_variance_extract,

        coalesce(f.forecast_line_rows, 0) as forecast_line_rows,
        coalesce(v.variance_extract_rows, 0) as variance_extract_rows,
        coalesce(v.actual_period_variance_rows, 0) as actual_period_variance_rows,
        coalesce(v.forecast_period_variance_rows, 0) as forecast_period_variance_rows,

        coalesce(b.actual_fs_allocated_rows, 0) as actual_fs_allocated_rows,
        coalesce(b.actual_workforce_subledger_rows, 0) as actual_workforce_subledger_rows,
        coalesce(b.scenario_driver_forecast_rows, 0) as scenario_driver_forecast_rows,
        f.distinct_forecast_basis_count,

        case
            when f.forecast_scenario = 'Base Case' then 10
            when f.forecast_scenario = 'Upside Case' then 20
            when f.forecast_scenario = 'Downside Case' then 30
            else 99
        end as scenario_sort,

        f.created_date,
        f.updated_date,

        false as is_unassigned

    from forecast_source as f
    left join forecast_basis_summary as b
        on f.forecast_scenario_nk = b.forecast_scenario_nk
    left join variance_extract as v
        on f.forecast_scenario_nk = v.forecast_scenario_nk

),

actuals_row as (

    select
        md5('ACTUALS') as forecast_scenario_hk,

        'ACTUALS' as forecast_scenario_nk,
        'ACTUALS' as forecast_version_code,
        'Actual Transactions' as forecast_scenario,
        'Actuals' as scenario_type,

        cast(null as integer) as fiscal_year,
        cast(null as date) as forecast_start_period,
        cast(null as date) as forecast_end_period,

        'ACTUALS' as source_budget_version_code,
        md5('ACTUALS') as source_budget_version_hk,

        true as is_actuals,

        false as is_base_case,
        false as is_upside_case,
        false as is_downside_case,

        true as is_locked,

        false as exists_in_forecast_lines,
        false as exists_in_variance_extract,

        0 as forecast_line_rows,
        0 as variance_extract_rows,
        0 as actual_period_variance_rows,
        0 as forecast_period_variance_rows,

        0 as actual_fs_allocated_rows,
        0 as actual_workforce_subledger_rows,
        0 as scenario_driver_forecast_rows,
        0 as distinct_forecast_basis_count,

        0 as scenario_sort,

        cast(null as date) as created_date,
        cast(null as date) as updated_date,

        false as is_unassigned

),

unassigned_row as (

    select
        md5('UNASSIGNED') as forecast_scenario_hk,

        'UNASSIGNED' as forecast_scenario_nk,
        'UNASSIGNED' as forecast_version_code,
        'Unassigned Forecast Scenario' as forecast_scenario,
        'Unassigned' as scenario_type,

        cast(null as integer) as fiscal_year,
        cast(null as date) as forecast_start_period,
        cast(null as date) as forecast_end_period,

        'UNASSIGNED' as source_budget_version_code,
        md5('UNASSIGNED') as source_budget_version_hk,

        false as is_actuals,

        false as is_base_case,
        false as is_upside_case,
        false as is_downside_case,

        false as is_locked,

        false as exists_in_forecast_lines,
        false as exists_in_variance_extract,

        0 as forecast_line_rows,
        0 as variance_extract_rows,
        0 as actual_period_variance_rows,
        0 as forecast_period_variance_rows,

        0 as actual_fs_allocated_rows,
        0 as actual_workforce_subledger_rows,
        0 as scenario_driver_forecast_rows,
        0 as distinct_forecast_basis_count,

        -1 as scenario_sort,

        cast(null as date) as created_date,
        cast(null as date) as updated_date,

        true as is_unassigned

)

select *
from unassigned_row

union all

select *
from actuals_row

union all

select *
from forecast_rows
