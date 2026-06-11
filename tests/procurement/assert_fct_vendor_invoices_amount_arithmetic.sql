/*
    Test: fct_vendor_invoices invoice amount arithmetic is valid.

    Failure condition:
    subtotal + tax does not equal total in local or GBP.
*/

select
    vendor_invoice_hk,
    vendor_invoice_id,
    vendor_id,
    invoice_number,
    currency_code,
    subtotal_local,
    tax_amount_local,
    total_local,
    invoice_arithmetic_variance_local,
    subtotal_gbp,
    tax_amount_gbp,
    total_gbp,
    invoice_arithmetic_variance_gbp
from {{ ref('fct_vendor_invoices') }}
where abs(invoice_arithmetic_variance_local) > 0.01
   or abs(invoice_arithmetic_variance_gbp) > 0.01
