/*
    Test: fct_billing_payment_allocations positive allocated amounts.

    Failure condition:
    Any allocation where local or GBP allocated amount is null, zero, or negative.
*/

select
    allocation_id,
    payment_id,
    invoice_id,
    allocation_status,
    currency_code,
    allocated_amount_local,
    allocated_amount_gbp
from {{ ref('fct_billing_payment_allocations') }}
where
    allocated_amount_local is null
    or allocated_amount_gbp is null
    or allocated_amount_local <= 0
    or allocated_amount_gbp <= 0
