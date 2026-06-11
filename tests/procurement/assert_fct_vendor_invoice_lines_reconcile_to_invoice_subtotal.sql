/*
    Test: fct_vendor_invoice_lines reconcile to vendor invoice header subtotal.

    Failure condition:
    Summed line amounts for an invoice do not agree to the parent invoice subtotal.
*/

select
    vendor_invoice_hk,
    vendor_invoice_id,
    invoice_line_subtotal_local,
    header_subtotal_local,
    invoice_subtotal_reconciliation_variance_local,
    invoice_line_subtotal_gbp,
    header_subtotal_gbp,
    invoice_subtotal_reconciliation_variance_gbp
from {{ ref('fct_vendor_invoice_lines') }}
where abs(invoice_subtotal_reconciliation_variance_local) > 0.01
   or abs(invoice_subtotal_reconciliation_variance_gbp) > 0.01
