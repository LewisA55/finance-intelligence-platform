{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'governance', 'model_readiness', 'modelling']
) }}

with source as (

    select *
    from {{ source('bronze', 'governance__model_readiness_controls') }}

),

renamed_and_casted as (

    select
        lower(trim(cast(control_key as varchar))) as control_key,
        nullif(trim(cast(control_name as varchar)), '') as control_name,
        nullif(trim(cast(control_domain as varchar)), '') as control_domain,
        nullif(trim(cast(severity as varchar)), '') as severity,
        coalesce({{ safecast_boolean('model_blocking_flag') }}, false) as model_blocking_flag,
        coalesce({{ safecast_boolean('accepted_limitation_flag') }}, false) as accepted_limitation_flag,
        nullif(trim(cast(recommended_treatment as varchar)), '') as recommended_treatment,

        _atlas_row_hash,
        cast(_atlas_ingested_at as timestamp) as _atlas_ingested_at,
        _atlas_source_file

    from source

)

select *
from renamed_and_casted
