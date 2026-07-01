{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'accounting', 'opening_balance_sheet', 'modelling']
) }}

with source as (

    select *
    from {{ source('bronze', 'accounting__opening_balance_sheet') }}

),

renamed_and_casted as (

    select
        {{ safecast_date('as_of_date') }} as as_of_date,

        {{ safecast_decimal('cash_gbp') }} as cash_gbp,
        {{ safecast_decimal('accounts_receivable_gbp') }} as accounts_receivable_gbp,
        {{ safecast_decimal('prepaids_other_current_assets_gbp') }} as prepaids_other_current_assets_gbp,
        {{ safecast_decimal('ppe_gbp') }} as ppe_gbp,
        {{ safecast_decimal('accumulated_depreciation_gbp') }} as accumulated_depreciation_gbp,
        {{ safecast_decimal('accounts_payable_gbp') }} as accounts_payable_gbp,
        {{ safecast_decimal('deferred_revenue_gbp') }} as deferred_revenue_gbp,
        {{ safecast_decimal('debt_gbp') }} as debt_gbp,
        {{ safecast_decimal('share_capital_gbp') }} as share_capital_gbp,
        {{ safecast_decimal('retained_earnings_gbp') }} as retained_earnings_gbp,

        nullif(trim(cast(source_system as varchar)), '') as source_system,
        nullif(trim(cast(model_note as varchar)), '') as model_note,

        _atlas_row_hash,
        cast(_atlas_ingested_at as timestamp) as _atlas_ingested_at,
        _atlas_source_file

    from source

)

select *
from renamed_and_casted
