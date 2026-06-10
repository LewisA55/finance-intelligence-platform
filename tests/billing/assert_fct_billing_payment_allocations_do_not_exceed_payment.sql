/*
    Test: payment allocations do not exceed parent payment amount.

    Failure condition:
    Total allocated GBP by payment_id exceeds the parent payment amount by more
    than 0.01. This is a hard O2C settlement control. Invoice over-application is
    tracked as an operational allocation status, but payment over-allocation is
    not allowed.
*/

with allocation_totals as (

    select
        payment_id,
        round(sum(allocated_amount_gbp), 2) as allocated_amount_gbp
    from {{ ref('fct_billing_payment_allocations') }}
    group by payment_id

)

select
    a.payment_id,
    a.allocated_amount_gbp,
    p.payment_amount_gbp,
    round(a.allocated_amount_gbp - p.payment_amount_gbp, 2) as over_allocated_gbp
from allocation_totals as a
left join {{ ref('fct_billing_payments') }} as p
    on trim(upper(a.payment_id)) = trim(upper(p.payment_id))
where a.allocated_amount_gbp > p.payment_amount_gbp + 0.01
