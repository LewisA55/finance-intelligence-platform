{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'accounting', 'financial_controls']
) }}

with source as (

    select *
    from {{ source('bronze', 'accounting__financial_statement_controls') }}

),

renamed_and_casted as (

    select
        -- Primary key
        trim(cast(control_pk as varchar)) as control_pk,

        -- Accounting period / currency
        trim(cast(posting_period as varchar)) as posting_period,
        upper(trim(cast(currency as varchar))) as control_currency_scope,

        -- Control classification
        trim(cast(control_check as varchar)) as control_check,
        trim(cast(control_category as varchar)) as control_category,

        -- Local-currency control values
        {{ safecast_decimal('expected_value_local') }} as expected_value_local,
        {{ safecast_decimal('actual_value_local') }} as actual_value_local,
        {{ safecast_decimal('variance_value_local') }} as variance_value_local,
        {{ safecast_decimal('absolute_variance_local') }} as absolute_variance_local,

        -- GBP control values
        {{ safecast_decimal('expected_value_gbp') }} as expected_value_gbp,
        {{ safecast_decimal('actual_value_gbp') }} as actual_value_gbp,
        {{ safecast_decimal('variance_value_gbp') }} as variance_value_gbp,
        {{ safecast_decimal('absolute_variance_gbp') }} as absolute_variance_gbp,

        -- Threshold / result classification
        {{ safecast_decimal('materiality_threshold') }} as materiality_threshold,
        trim(cast(control_status as varchar)) as control_status,
        trim(cast(severity as varchar)) as severity,

        -- Source lineage / narrative
        trim(cast(source_dataset as varchar)) as source_dataset,
        nullif(trim(cast(description as varchar)), '') as description,

        -- Operational flags
        {{ safecast_boolean('is_system_generated') }} as is_system_generated,

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
