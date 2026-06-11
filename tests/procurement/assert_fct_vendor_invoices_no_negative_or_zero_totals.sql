/*
    Test: fct_vendor_invoices does not contain negative or zero-value invoice totals.

    Failure condition:
    A vendor invoice has total_gbp less than or equal to zero.
*/

select
    vendor_invoice_hk,
    vendor_invoice_id,
    vendor_id,
    invoice_number,
    total_gbp,
    is_negative_invoice_total,
    is_zero_invoice_total
from {{ ref('fct_vendor_invoices') }}
where total_gbp <= 0
