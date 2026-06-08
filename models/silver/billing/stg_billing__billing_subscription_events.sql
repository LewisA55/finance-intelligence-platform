{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'billing', 'subscription_events']
) }}

with source as (

    select *
    from {{ source('bronze', 'billing__billing_subscription_events') }}

),

renamed_and_casted as (

    select
        trim(cast(event_pk as varchar)) as event_pk,
        trim(cast(event_id as varchar)) as event_id,
        trim(cast(subscription_id as varchar)) as subscription_id,
        trim(cast(customer_id as varchar)) as customer_id,

        cast(try_cast(nullif(trim(cast(event_sequence as varchar)), '') as integer) as integer) as event_sequence,
        {{ safecast_date('event_date') }} as event_date,
        case
            when lower(trim(cast(event_type as varchar))) = 'new' then 'New'
            when lower(trim(cast(event_type as varchar))) = 'renewal' then 'Renewal'
            when lower(trim(cast(event_type as varchar))) = 'expansion' then 'Expansion'
            when lower(trim(cast(event_type as varchar))) = 'contraction' then 'Contraction'
            when lower(trim(cast(event_type as varchar))) = 'price_increase' then 'Price Increase'
            when lower(trim(cast(event_type as varchar))) = 'churn' then 'Churn'
            when lower(trim(cast(event_type as varchar))) = 'pause' then 'Pause'
            else null
        end as event_type,
        nullif(trim(cast(event_reason as varchar)), '') as event_reason,

        {{ safecast_decimal('previous_mrr_local') }} as previous_mrr_local,
        {{ safecast_decimal('new_mrr_local') }} as new_mrr_local,
        {{ safecast_decimal('mrr_delta_local') }} as mrr_delta_local,
        {{ safecast_decimal('previous_mrr_gbp') }} as previous_mrr_gbp,
        {{ safecast_decimal('new_mrr_gbp') }} as new_mrr_gbp,
        {{ safecast_decimal('mrr_delta_gbp') }} as mrr_delta_gbp,

        {{ safecast_decimal('previous_arr_local') }} as previous_arr_local,
        {{ safecast_decimal('new_arr_local') }} as new_arr_local,
        {{ safecast_decimal('arr_delta_local') }} as arr_delta_local,
        {{ safecast_decimal('previous_arr_gbp') }} as previous_arr_gbp,
        {{ safecast_decimal('new_arr_gbp') }} as new_arr_gbp,
        {{ safecast_decimal('arr_delta_gbp') }} as arr_delta_gbp,

        upper(trim(cast(currency as varchar))) as currency,
        trim(cast(source_system as varchar)) as source_system,

        {{ safecast_boolean('is_terminal_event') }} as is_terminal_event,
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
