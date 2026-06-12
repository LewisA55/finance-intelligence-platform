{{ config(
    materialized = 'table',
    schema = 'gold'
) }}

with source as (

    select *
    from {{ ref('stg_billing__billing_subscription_events') }}

),

subscriptions as (

    select
        subscription_id,
        customer_id as subscription_customer_id,
        product_id,
        customer_segment,
        plan_tier,
        contract_status,
        billing_frequency,
        contract_start_date,
        contract_end_date,
        arr_gbp as subscription_current_arr_gbp,
        mrr_gbp as subscription_current_mrr_gbp,
        is_defect as is_subscription_defect,
        defect_type as subscription_defect_type
    from {{ ref('stg_billing__billing_subscriptions') }}

),

dim_customer as (

    select
        customer_hk,
        customer_id,
        region_hk
    from {{ ref('dim_customer') }}

),

dim_region as (

    select
        region_hk
    from {{ ref('dim_region') }}

),

dim_date as (

    select
        date_hk,
        date_day
    from {{ ref('dim_date') }}
    where date_day is not null

),

final as (

    select
        -- Primary key
        source.event_pk as subscription_event_hk,
        source.event_id,

        -- Conformed dimension keys
        coalesce(event_date.date_hk, md5('UNASSIGNED')) as event_date_hk,
        coalesce(dim_customer.customer_hk, md5('UNASSIGNED')) as customer_hk,
        coalesce(dim_customer.region_hk, md5('UNASSIGNED')) as region_hk,

        -- Degenerate / operational keys
        source.subscription_id,
        source.customer_id,
        subscriptions.product_id,
        subscriptions.customer_segment,
        subscriptions.plan_tier,
        subscriptions.contract_status,
        subscriptions.billing_frequency,
        subscriptions.contract_start_date,
        subscriptions.contract_end_date,

        -- Event descriptors
        source.event_sequence,
        source.event_date,
        cast(date_trunc('month', source.event_date) as date) as event_month_date,
        source.event_type,
        source.event_reason,
        source.currency as currency_code,

        -- Source MRR / ARR state values
        source.previous_mrr_local,
        source.new_mrr_local,
        source.mrr_delta_local,
        source.previous_mrr_gbp,
        source.new_mrr_gbp,
        source.mrr_delta_gbp,

        source.previous_arr_local,
        source.new_arr_local,
        source.arr_delta_local,
        source.previous_arr_gbp,
        source.new_arr_gbp,
        source.arr_delta_gbp,

        -- Subscription master current state for context only
        subscriptions.subscription_current_arr_gbp,
        subscriptions.subscription_current_mrr_gbp,

        -- ARR movement vectors.
        -- Negative vectors are stored as positive analytical amounts for waterfall reporting.
        case
            when source.event_type = 'New' and source.arr_delta_gbp > 0
                then source.arr_delta_gbp
            else 0
        end as new_business_arr_gbp,

        case
            when source.event_type = 'Expansion' and source.arr_delta_gbp > 0
                then source.arr_delta_gbp
            else 0
        end as expansion_arr_gbp,

        case
            when source.event_type = 'Price Increase' and source.arr_delta_gbp > 0
                then source.arr_delta_gbp
            else 0
        end as price_increase_arr_gbp,

        case
            when source.event_type in ('Expansion', 'Price Increase') and source.arr_delta_gbp > 0
                then source.arr_delta_gbp
            else 0
        end as gross_expansion_arr_gbp,

        case
            when source.event_type = 'Contraction' and source.arr_delta_gbp < 0
                then abs(source.arr_delta_gbp)
            else 0
        end as contraction_arr_gbp,

        case
            when source.event_type = 'Churn' and source.arr_delta_gbp < 0
                then abs(source.arr_delta_gbp)
            else 0
        end as churn_arr_gbp,

        case
            when source.event_type = 'Pause' and source.arr_delta_gbp < 0
                then abs(source.arr_delta_gbp)
            else 0
        end as pause_arr_gbp,

        case
            when source.event_type = 'Renewal'
                then source.arr_delta_gbp
            else 0
        end as renewal_arr_delta_gbp,

        source.arr_delta_gbp as net_arr_delta_gbp,
        source.mrr_delta_gbp as net_mrr_delta_gbp,

        -- Event classification flags
        source.event_type = 'New' as is_new_event,
        source.event_type = 'Renewal' as is_renewal_event,
        source.event_type = 'Expansion' as is_expansion_event,
        source.event_type = 'Price Increase' as is_price_increase_event,
        source.event_type = 'Contraction' as is_contraction_event,
        source.event_type = 'Churn' as is_churn_event,
        source.event_type = 'Pause' as is_pause_event,
        source.is_terminal_event,

        -- Control / exception telemetry
        subscriptions.subscription_id is null as has_missing_subscription_master,

        round(
            source.previous_arr_gbp
            + source.arr_delta_gbp
            - source.new_arr_gbp,
            2
        ) as arr_identity_variance_gbp,

        round(
            source.previous_mrr_gbp
            + source.mrr_delta_gbp
            - source.new_mrr_gbp,
            2
        ) as mrr_identity_variance_gbp,

        round(
            source.previous_arr_gbp
            + source.arr_delta_gbp
            - source.new_arr_gbp,
            2
        ) <> 0 as has_arr_identity_break,

        round(
            source.previous_mrr_gbp
            + source.mrr_delta_gbp
            - source.new_mrr_gbp,
            2
        ) <> 0 as has_mrr_identity_break,

        source.is_defect,
        source.defect_type,
        coalesce(subscriptions.is_subscription_defect, false) as is_subscription_defect,
        subscriptions.subscription_defect_type,

        -- Source context
        source.source_system,
        source.created_date,
        source.updated_date,

        -- Atlas lineage
        source._atlas_row_hash,
        source._atlas_ingested_at,
        source._atlas_source_file

    from source

    left join subscriptions
        on source.subscription_id = subscriptions.subscription_id

    left join dim_customer
        on source.customer_id = dim_customer.customer_id

    left join dim_region
        on dim_customer.region_hk = dim_region.region_hk

    left join dim_date as event_date
        on source.event_date = event_date.date_day

)

select *
from final
