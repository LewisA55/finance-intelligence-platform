{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'core_fact', 'budget']
) }}

with source as (

    select
        budget_line_pk,
        budget_line_id,
        budget_version_code,
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

        budget_amount_local,
        budget_amount_gbp,

        planning_driver,
        driver_quantity,
        driver_rate,
        budget_method,

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

    from {{ ref('stg_planning__budget_lines') }}

),

renamed as (

    select
        md5(trim(upper(cast(budget_line_id as varchar)))) as budget_line_hk,

        budget_line_pk,
        budget_line_id,

        case
            when budget_version_code is not null and trim(cast(budget_version_code as varchar)) <> ''
            then md5(trim(upper(cast(budget_version_code as varchar))))
            else md5('UNASSIGNED')
        end as budget_version_hk,

        case
            when posting_period is not null
            then md5(strftime(posting_period, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as budget_date_hk,

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

        nullif(trim(upper(cast(budget_version_code as varchar))), '') as budget_version_code,

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

        coalesce(budget_amount_local, 0) as budget_amount_local,
        coalesce(budget_amount_gbp, 0) as budget_amount_gbp,

        planning_driver,
        coalesce(driver_quantity, 0) as driver_quantity,
        coalesce(driver_rate, 0) as driver_rate,
        budget_method,

        coalesce(is_locked, false) as is_locked,
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
