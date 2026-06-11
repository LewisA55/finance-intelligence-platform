/*
    Test: fct_vendor_invoices payment status flags are mutually exclusive.

    Failure condition:
    A row is not classified as exactly one of paid, open, or overdue.
*/

select
    vendor_invoice_hk,
    vendor_invoice_id,
    payment_status,
    is_paid,
    is_open,
    is_overdue
from {{ ref('fct_vendor_invoices') }}
where (
        cast(is_paid as integer)
        + cast(is_open as integer)
        + cast(is_overdue as integer)
      ) <> 1
