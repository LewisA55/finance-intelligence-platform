/*
    Test: vendor payments do not exceed parent invoice total.

    Failure condition:
    Total payments for a vendor invoice exceed the invoice total.
*/

select distinct
    vendor_invoice_hk,
    vendor_invoice_id,
    invoice_total_gbp,
    invoice_paid_amount_gbp,
    invoice_paid_vs_total_variance_gbp,
    is_payment_exceeds_invoice_total
from {{ ref('fct_vendor_payments') }}
where is_payment_exceeds_invoice_total = true
   or invoice_paid_amount_gbp > invoice_total_gbp + 0.01
