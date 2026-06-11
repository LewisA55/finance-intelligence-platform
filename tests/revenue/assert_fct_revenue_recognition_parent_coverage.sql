/*
    Test: fct_revenue_recognition parent links are complete.

    Failure condition:
    A recognition row does not link to its invoice, invoice line, or customer.
*/

select
    revenue_recognition_hk,
    recognition_id,
    invoice_id,
    invoice_line_id,
    customer_id,
    is_orphan_invoice_recognition,
    is_orphan_invoice_line_recognition,
    is_orphan_customer_recognition
from {{ ref('fct_revenue_recognition') }}
where is_orphan_invoice_recognition = true
   or is_orphan_invoice_line_recognition = true
   or is_orphan_customer_recognition = true
