{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'billing', 'ar_ageing']
) }}

with source as (

    select *
    from {{ source('bronze', 'billing__ar_ageing_snapshot') }}

),

renamed_and_casted as (

    select
        trim(cast(snapshot_pk as varchar)) as snapshot_pk,
        {{ safecast_date('snapshot_date') }} as snapshot_date,

        trim(cast(invoice_id as varchar)) as invoice_id,
        trim(cast(customer_id as varchar)) as customer_id,

        {{ safecast_date('invoice_date') }} as invoice_date,
        {{ safecast_date('due_date') }} as due_date,

        upper(trim(cast(currency as varchar))) as currency,

        {{ safecast_decimal('invoice_total_local') }} as invoice_total_local,
        {{ safecast_decimal('invoice_total_gbp') }} as invoice_total_gbp,
        {{ safecast_decimal('paid_amount_local') }} as paid_amount_local,
        {{ safecast_decimal('paid_amount_gbp') }} as paid_amount_gbp,
        {{ safecast_decimal('open_amount_local') }} as open_amount_local,
        {{ safecast_decimal('open_amount_gbp') }} as open_amount_gbp,

        cast(try_cast(nullif(trim(cast(days_past_due as varchar)), '') as integer) as integer) as days_past_due,

        trim(cast(ageing_bucket as varchar)) as ageing_bucket,
        trim(cast(ar_status as varchar)) as ar_status,
        trim(cast(collection_status as varchar)) as collection_status,

        {{ safecast_boolean('is_disputed_flag') }} as is_disputed,
        {{ safecast_boolean('is_writeoff_candidate_flag') }} as is_writeoff_candidate,

        trim(cast(source_system as varchar)) as source_system,
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
