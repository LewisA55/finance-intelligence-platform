{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'accounting', 'chart_of_accounts']
) }}

with source as (

    select *
    from {{ source('bronze', 'accounting__chart_of_accounts') }}

),

renamed_and_casted as (

    select
        -- Primary key
        trim(cast(account_pk as varchar)) as account_pk,

        -- Natural / business keys
        trim(cast(account_code as varchar)) as account_code,

        -- Descriptive attributes
        trim(cast(account_name as varchar)) as account_name,
        trim(cast(account_class as varchar)) as account_class,
        trim(cast(account_type as varchar)) as account_type,
        trim(cast(financial_statement as varchar)) as financial_statement,
        trim(cast(report_group as varchar)) as report_group,
        trim(cast(report_subgroup as varchar)) as report_subgroup,
        trim(cast(normal_balance as varchar)) as normal_balance,

        -- Boolean flags
        {{ safecast_boolean('is_pnl') }} as is_pnl,
        {{ safecast_boolean('is_balance_sheet') }} as is_balance_sheet,
        {{ safecast_boolean('is_cash_account') }} as is_cash_account,
        {{ safecast_boolean('is_control_account') }} as is_control_account,
        {{ safecast_boolean('active_flag') }} as is_active,

        -- Source operational dates
        {{ safecast_date('created_at') }} as created_date,
        {{ safecast_date('updated_at') }} as updated_date,

        -- Atlas Bronze lineage metadata
        _atlas_row_hash,
        cast(_atlas_ingested_at as timestamp) as _atlas_ingested_at,
        _atlas_source_file

    from source

)

select *
from renamed_and_casted
