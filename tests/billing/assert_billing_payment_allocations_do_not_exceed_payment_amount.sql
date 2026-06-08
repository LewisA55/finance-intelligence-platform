/*
Purpose:
    Reconcile payment allocations back to the payment transaction amount and
    identify payments where allocated value exceeds cash received without being
    explicitly marked as an over-applied allocation case.

Grain:
    One failing row per payment_id.

Expected result:
    Zero rows.

Notes:
    Payments containing allocation_status = 'Over Applied' are excluded from
    this control because over-application is an intentional operational state
    captured explicitly in the allocation layer.
*/

with allocation_totals as (

    select
        payment_id,
        round(sum(allocated_amount_local), 2) as allocated_amount_local,
        round(sum(allocated_amount_gbp), 2) as allocated_amount_gbp,
        max(case when allocation_status = 'Over Applied' then 1 else 0 end) as has_over_applied_allocation
    from {{ ref('stg_billing__billing_payment_allocations') }}
    group by payment_id

),

payments as (

    select
        payment_id,
        round(payment_amount_local, 2) as payment_amount_local,
        round(payment_amount_gbp, 2) as payment_amount_gbp,
        payment_status
    from {{ ref('stg_billing__billing_payments') }}

)

select
    payments.payment_id,
    payments.payment_status,
    payments.payment_amount_local,
    allocation_totals.allocated_amount_local,
    payments.payment_amount_gbp,
    allocation_totals.allocated_amount_gbp,
    round(allocation_totals.allocated_amount_local - payments.payment_amount_local, 2) as local_over_allocated_amount,
    round(allocation_totals.allocated_amount_gbp - payments.payment_amount_gbp, 2) as gbp_over_allocated_amount
from payments
inner join allocation_totals
    on payments.payment_id = allocation_totals.payment_id
where
    allocation_totals.has_over_applied_allocation = 0
    and (
        allocation_totals.allocated_amount_local > payments.payment_amount_local + 0.01
        or allocation_totals.allocated_amount_gbp > payments.payment_amount_gbp + 0.01
    )
