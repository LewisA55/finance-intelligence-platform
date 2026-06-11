/*
    Test: fct_vendor_payments contains only positive payment amounts.

    Failure condition:
    A vendor payment has payment_amount_gbp less than or equal to zero.
*/

select
    vendor_payment_hk,
    vendor_payment_id,
    vendor_invoice_id,
    payment_amount_gbp,
    is_positive_payment,
    is_negative_payment,
    is_zero_payment
from {{ ref('fct_vendor_payments') }}
where payment_amount_gbp <= 0
   or is_positive_payment = false
