{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'accounting', 'financial_statements']
) }}

with source as (

    select *
    from {{ source('bronze', 'accounting__financial_statement_extract') }}

),

renamed_and_casted as (

    select
        -- Primary key
        trim(cast(financial_statement_pk as varchar)) as financial_statement_pk,

        -- Accounting period
        trim(cast(posting_period as varchar)) as posting_period,
        {{ safecast_date('period_start_date') }} as period_start_date,
        {{ safecast_date('period_end_date') }} as period_end_date,

        -- Statement hierarchy
        trim(cast(statement_type as varchar)) as statement_type,
        cast(try_cast(nullif(trim(cast(statement_type_sort as varchar)), '') as integer) as integer) as statement_type_sort,
        trim(cast(statement_section as varchar)) as statement_section,
        cast(try_cast(nullif(trim(cast(statement_section_sort as varchar)), '') as integer) as integer) as statement_section_sort,
        trim(cast(statement_line as varchar)) as statement_line,
        cast(try_cast(nullif(trim(cast(statement_line_sort as varchar)), '') as integer) as integer) as statement_line_sort,

        -- Account attributes
        nullif(trim(cast(account_code as varchar)), '') as account_code,
        nullif(trim(cast(account_name as varchar)), '') as account_name,
        nullif(trim(cast(account_class as varchar)), '') as account_class,

        -- Currency and amounts
        upper(trim(cast(currency as varchar))) as currency,
        {{ safecast_decimal('amount_local') }} as amount_local,
        {{ safecast_decimal('amount_gbp') }} as amount_gbp,
        cast(try_cast(nullif(trim(cast(presentation_sign_multiplier as varchar)), '') as integer) as integer) as presentation_sign_multiplier,

        -- Presentation / calculation metadata
        {{ safecast_boolean('is_calculated_line') }} as is_calculated_line,
        nullif(trim(cast(calculation_type as varchar)), '') as calculation_type,

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
