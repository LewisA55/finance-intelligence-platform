{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'core_dimension', 'budget_version']
) }}

with budget_master as (

    select
        trim(upper(cast(budget_version_code as varchar))) as budget_version_code,

        budget_version_pk,
        nullif(trim(cast(budget_name as varchar)), '') as budget_name,
        fiscal_year,
        coalesce(nullif(trim(cast(scenario_type as varchar)), ''), 'Unknown') as scenario_type,
        coalesce(nullif(trim(cast(approval_status as varchar)), ''), 'Unknown') as approval_status,
        nullif(trim(cast(approved_by as varchar)), '') as approved_by,
        approval_date,
        coalesce(is_locked, false) as is_locked,
        planning_start_period,
        planning_end_period,
        coalesce(nullif(trim(cast(source_system as varchar)), ''), 'Unknown') as source_system,
        created_date,
        updated_date,

        _atlas_row_hash,
        _atlas_ingested_at,
        _atlas_source_file

    from {{ ref('stg_planning__budget_versions') }}
    where budget_version_code is not null
      and trim(budget_version_code) <> ''

),

budget_lines as (

    select
        trim(upper(cast(budget_version_code as varchar))) as budget_version_code,
        count(*) as budget_line_rows
    from {{ ref('stg_planning__budget_lines') }}
    where budget_version_code is not null
      and trim(budget_version_code) <> ''
    group by trim(upper(cast(budget_version_code as varchar)))

),

forecast_lines as (

    select
        trim(upper(cast(source_budget_version_code as varchar))) as budget_version_code,
        count(*) as forecast_line_rows
    from {{ ref('stg_planning__forecast_lines') }}
    where source_budget_version_code is not null
      and trim(source_budget_version_code) <> ''
    group by trim(upper(cast(source_budget_version_code as varchar)))

),

variance_extract as (

    select
        trim(upper(cast(budget_version_code as varchar))) as budget_version_code,
        count(*) as variance_extract_rows,
        sum(case when period_status = 'Actual' then 1 else 0 end) as actual_period_variance_rows,
        sum(case when period_status = 'Forecast' then 1 else 0 end) as forecast_period_variance_rows
    from {{ ref('stg_planning__variance_source_extract') }}
    where budget_version_code is not null
      and trim(budget_version_code) <> ''
    group by trim(upper(cast(budget_version_code as varchar)))

),

budget_rows as (

    select
        md5(m.budget_version_code) as budget_version_hk,

        m.budget_version_pk,
        m.budget_version_code,
        m.budget_name,
        m.fiscal_year,
        m.scenario_type,
        m.approval_status,
        m.approved_by,
        m.approval_date,
        m.is_locked,

        case
            when m.is_locked = true
             and m.approval_status = 'Approved'
             and m.budget_version_code like '%BOARD_APPROVED%'
            then true
            else false
        end as is_board_approved_budget,

        case
            when m.budget_version_code like '%ORIGINAL%' then true
            else false
        end as is_original_budget,

        false as is_actuals,

        m.planning_start_period,
        m.planning_end_period,

        m.source_system,
        m.created_date,
        m.updated_date,

        case when coalesce(b.budget_line_rows, 0) > 0 then true else false end as exists_in_budget_lines,
        case when coalesce(f.forecast_line_rows, 0) > 0 then true else false end as exists_in_forecast_lines,
        case when coalesce(v.variance_extract_rows, 0) > 0 then true else false end as exists_in_variance_extract,

        coalesce(b.budget_line_rows, 0) as budget_line_rows,
        coalesce(f.forecast_line_rows, 0) as forecast_line_rows,
        coalesce(v.variance_extract_rows, 0) as variance_extract_rows,
        coalesce(v.actual_period_variance_rows, 0) as actual_period_variance_rows,
        coalesce(v.forecast_period_variance_rows, 0) as forecast_period_variance_rows,

        case
            when m.budget_version_code like '%BOARD_APPROVED%' then 10
            when m.budget_version_code like '%ORIGINAL%' then 20
            else 99
        end as budget_version_sort,

        case
            when m.approval_status = 'Approved' then 10
            when m.approval_status = 'Draft' then 20
            else 99
        end as approval_status_sort,

        m._atlas_row_hash,
        m._atlas_ingested_at,
        m._atlas_source_file,

        false as is_unassigned

    from budget_master as m
    left join budget_lines as b
        on m.budget_version_code = b.budget_version_code
    left join forecast_lines as f
        on m.budget_version_code = f.budget_version_code
    left join variance_extract as v
        on m.budget_version_code = v.budget_version_code

),

actuals_row as (

    select
        md5('ACTUALS') as budget_version_hk,

        'ACTUALS_BUDGET_VERSION' as budget_version_pk,
        'ACTUALS' as budget_version_code,
        'Actual Transactions' as budget_name,
        cast(null as integer) as fiscal_year,
        'Actuals' as scenario_type,
        'Actuals' as approval_status,
        cast(null as varchar) as approved_by,
        cast(null as date) as approval_date,
        true as is_locked,

        false as is_board_approved_budget,
        false as is_original_budget,
        true as is_actuals,

        cast(null as date) as planning_start_period,
        cast(null as date) as planning_end_period,

        'Gold System Row' as source_system,
        cast(null as date) as created_date,
        cast(null as date) as updated_date,

        false as exists_in_budget_lines,
        false as exists_in_forecast_lines,
        false as exists_in_variance_extract,

        0 as budget_line_rows,
        0 as forecast_line_rows,
        0 as variance_extract_rows,
        0 as actual_period_variance_rows,
        0 as forecast_period_variance_rows,

        0 as budget_version_sort,
        0 as approval_status_sort,

        cast(null as varchar) as _atlas_row_hash,
        cast(null as timestamp) as _atlas_ingested_at,
        cast(null as varchar) as _atlas_source_file,

        false as is_unassigned

),

unassigned_row as (

    select
        md5('UNASSIGNED') as budget_version_hk,

        'UNASSIGNED_BUDGET_VERSION' as budget_version_pk,
        'UNASSIGNED' as budget_version_code,
        'Unassigned Budget Version' as budget_name,
        cast(null as integer) as fiscal_year,
        'Unassigned' as scenario_type,
        'Unassigned' as approval_status,
        cast(null as varchar) as approved_by,
        cast(null as date) as approval_date,
        false as is_locked,

        false as is_board_approved_budget,
        false as is_original_budget,
        false as is_actuals,

        cast(null as date) as planning_start_period,
        cast(null as date) as planning_end_period,

        'Gold System Row' as source_system,
        cast(null as date) as created_date,
        cast(null as date) as updated_date,

        false as exists_in_budget_lines,
        false as exists_in_forecast_lines,
        false as exists_in_variance_extract,

        0 as budget_line_rows,
        0 as forecast_line_rows,
        0 as variance_extract_rows,
        0 as actual_period_variance_rows,
        0 as forecast_period_variance_rows,

        -1 as budget_version_sort,
        -1 as approval_status_sort,

        cast(null as varchar) as _atlas_row_hash,
        cast(null as timestamp) as _atlas_ingested_at,
        cast(null as varchar) as _atlas_source_file,

        true as is_unassigned

)

select *
from unassigned_row

union all

select *
from actuals_row

union all

select *
from budget_rows
