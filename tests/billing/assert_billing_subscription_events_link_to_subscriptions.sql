/*
Purpose:
    Ensure every clean subscription event links to a known Billing subscription.

Grain:
    One failing row per clean event_id whose subscription_id is missing from
    silver.stg_billing__billing_subscriptions.

Expected result:
    Zero rows.

Notes:
    Intentional event-ledger defects such as GHOST_EVENT are excluded from this
    clean relationship control and should be surfaced separately in control /
    exception marts.
*/

with events as (

    select
        event_id,
        subscription_id,
        customer_id
    from {{ ref('stg_billing__billing_subscription_events') }}
    where is_defect = false

),

subscriptions as (

    select
        subscription_id,
        customer_id
    from {{ ref('stg_billing__billing_subscriptions') }}

)

select
    events.event_id,
    events.subscription_id,
    events.customer_id
from events
left join subscriptions
    on events.subscription_id = subscriptions.subscription_id
where subscriptions.subscription_id is null