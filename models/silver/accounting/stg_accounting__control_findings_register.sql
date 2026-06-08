{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'accounting', 'control_findings']
) }}

with source as (

    select *
    from {{ source('bronze', 'accounting__control_findings_register') }}

),

renamed_and_casted as (

    select
        -- Primary keys / identifiers
        trim(cast(finding_pk as varchar)) as finding_pk,
        trim(cast(finding_id as varchar)) as finding_id,

        -- Finding narrative
        trim(cast(finding_title as varchar)) as finding_title,
        nullif(trim(cast(finding_description as varchar)), '') as finding_description,

        -- Control linkage
        trim(cast(control_check as varchar)) as control_check,
        trim(cast(control_category as varchar)) as control_category,
        trim(cast(root_cause_category as varchar)) as root_cause_category,
        trim(cast(financial_statement_area as varchar)) as financial_statement_area,

        -- Ownership / scope
        trim(cast(owner_team as varchar)) as owner_team,
        nullif(trim(cast(affected_currencies as varchar)), '') as affected_currencies,
        cast(try_cast(nullif(trim(cast(affected_currency_count as varchar)), '') as integer) as integer) as affected_currency_count,

        -- Failure period range
        trim(cast(first_failed_period as varchar)) as first_failed_period,
        trim(cast(latest_failed_period as varchar)) as latest_failed_period,
        cast(try_cast(nullif(trim(cast(failed_control_row_count as varchar)), '') as integer) as integer) as failed_control_row_count,

        -- Source control row lineage
        nullif(trim(cast(source_control_row_ids as varchar)), '') as source_control_row_ids,

        -- Financial exposure
        {{ safecast_decimal('largest_variance_gbp') }} as largest_variance_gbp,
        {{ safecast_decimal('latest_variance_gbp') }} as latest_variance_gbp,

        -- Risk / lifecycle status
        trim(cast(risk_rating as varchar)) as risk_rating,
        trim(cast(severity as varchar)) as severity,
        trim(cast(finding_status as varchar)) as finding_status,

        -- Remediation
        nullif(trim(cast(remediation_action as varchar)), '') as remediation_action,
        {{ safecast_date('target_resolution_date') }} as target_resolution_date,

        -- Source lineage
        nullif(trim(cast(source_dataset as varchar)), '') as source_dataset,
        trim(cast(source_system as varchar)) as source_system,
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
