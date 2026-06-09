{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'workforce', 'headcount_plan']
) }}

with source as (

    select *
    from {{ source('bronze', 'workforce__headcount_plan') }}

),

renamed_and_casted as (

    select
        trim(cast(position_pk as varchar)) as position_pk,
        trim(cast(position_id as varchar)) as position_id,

        nullif(trim(cast(employee_id as varchar)), '') as employee_id,

        trim(cast(plan_status as varchar)) as plan_status,

        trim(cast(department_id as varchar)) as department_id,
        trim(cast(region_id as varchar)) as region_id,
        upper(trim(cast(country_code as varchar))) as country_code,
        upper(trim(cast(currency as varchar))) as currency,

        trim(cast(role_family as varchar)) as role_family,
        trim(cast(seniority_level as varchar)) as seniority_level,

        {{ safecast_date('planned_hire_date') }} as planned_hire_date,
        cast(date_trunc('month', {{ safecast_date('planned_hire_date') }}) as date) as planned_start_period,

        {{ safecast_decimal('target_salary_low_local') }} as target_salary_low_local,
        {{ safecast_decimal('target_salary_mid_local') }} as target_salary_mid_local,
        {{ safecast_decimal('target_salary_high_local') }} as target_salary_high_local,
        {{ safecast_decimal('target_salary_mid_gbp') }} as target_salary_mid_gbp,
        {{ safecast_decimal('fx_rate_to_gbp') }} as fx_rate_to_gbp,

        {{ safecast_boolean('backfill_flag') }} as is_backfill,
        trim(cast(source_system as varchar)) as source_system,
        {{ safecast_boolean('is_system_generated') }} as is_system_generated,
        {{ safecast_boolean('is_defect_flag') }} as is_defect,
        nullif(trim(cast(defect_type as varchar)), '') as defect_type,

        {{ safecast_date('created_at') }} as created_date,
        {{ safecast_date('updated_at') }} as updated_date,

        _atlas_row_hash,
        cast(_atlas_ingested_at as timestamp) as _atlas_ingested_at,
        _atlas_source_file

    from source

)

select *
from renamed_and_casted
