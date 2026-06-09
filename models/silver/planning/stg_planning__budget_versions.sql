{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'planning', 'budget_versions']
) }}

with source as (

    select *
    from {{ source('bronze', 'planning__budget_versions') }}

),

renamed_and_casted as (

    select
        trim(cast(budget_version_pk as varchar)) as budget_version_pk,
        trim(cast(budget_version_code as varchar)) as budget_version_code,
        trim(cast(budget_name as varchar)) as budget_name,

        cast(fiscal_year as integer) as fiscal_year,

        trim(cast(scenario_type as varchar)) as scenario_type,
        trim(cast(approval_status as varchar)) as approval_status,
        trim(cast(approved_by as varchar)) as approved_by,
        {{ safecast_date('approval_date') }} as approval_date,

        {{ safecast_boolean('is_locked_flag') }} as is_locked,

        strptime(trim(cast(planning_start_period as varchar)) || '-01', '%Y-%m-%d')::date as planning_start_period,
        strptime(trim(cast(planning_end_period as varchar)) || '-01', '%Y-%m-%d')::date as planning_end_period,

        trim(cast(source_system as varchar)) as source_system,
        {{ safecast_date('created_at') }} as created_date,
        {{ safecast_date('updated_at') }} as updated_date,

        _atlas_row_hash,
        cast(_atlas_ingested_at as timestamp) as _atlas_ingested_at,
        _atlas_source_file

    from source

)

select *
from renamed_and_casted
