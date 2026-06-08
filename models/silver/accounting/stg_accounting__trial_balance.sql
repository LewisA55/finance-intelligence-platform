{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'accounting', 'trial_balance']
) }}

with source as (

    select *
    from {{ source('bronze', 'accounting__trial_balance') }}

),

renamed_and_casted as (

    select
        -- Primary key
        trim(cast(trial_balance_pk as varchar)) as trial_balance_pk,

        -- Accounting period
        trim(cast(posting_period as varchar)) as posting_period,
        {{ safecast_date('period_start_date') }} as period_start_date,
        {{ safecast_date('period_end_date') }} as period_end_date,

        -- Account attributes
        trim(cast(account_code as varchar)) as account_code,
        trim(cast(account_name as varchar)) as account_name,
        trim(cast(account_class as varchar)) as account_class,
        trim(cast(financial_statement as varchar)) as financial_statement,

        -- Currency
        upper(trim(cast(currency as varchar))) as currency,

        -- Local-currency balances and movement
        {{ safecast_decimal('opening_balance_local') }} as opening_balance_local,
        {{ safecast_decimal('period_debits_local') }} as period_debits_local,
        {{ safecast_decimal('period_credits_local') }} as period_credits_local,
        {{ safecast_decimal('closing_balance_local') }} as closing_balance_local,

        -- GBP balances and movement
        {{ safecast_decimal('opening_balance_gbp') }} as opening_balance_gbp,
        {{ safecast_decimal('period_debits_gbp') }} as period_debits_gbp,
        {{ safecast_decimal('period_credits_gbp') }} as period_credits_gbp,
        {{ safecast_decimal('closing_balance_gbp') }} as closing_balance_gbp,

        -- Source / defect metadata
        trim(cast(source_system as varchar)) as source_system,
        {{ safecast_boolean('is_system_generated') }} as is_system_generated,
        {{ safecast_boolean('is_defect_flag') }} as is_defect,
        nullif(trim(cast(defect_type as varchar)), '') as defect_type,

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
