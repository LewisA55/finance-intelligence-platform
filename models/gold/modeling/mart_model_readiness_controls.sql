{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'mart', 'modelling', 'governance', 'model_readiness']
) }}

with source as (

    select *
    from {{ ref('stg_governance__model_readiness_controls') }}

),

final as (

    select
        md5(upper(control_key)) as model_readiness_control_hk,
        control_key,
        control_name,
        control_domain,
        severity,
        model_blocking_flag,
        accepted_limitation_flag,
        case
            when model_blocking_flag then 'Model Blocking'
            when accepted_limitation_flag then 'Accepted Limitation'
            when severity in ('High', 'Medium') then 'Usable with review'
            else 'Monitor'
        end as model_readiness_treatment,
        recommended_treatment,
        current_timestamp as _atlas_modelled_at
    from source

)

select *
from final
