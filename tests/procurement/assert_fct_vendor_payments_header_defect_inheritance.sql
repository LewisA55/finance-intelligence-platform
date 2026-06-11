/*
    Test: fct_vendor_payments inherit parent invoice defect flags.

    Failure condition:
    A payment attached to a defective invoice is not marked with an AP payment
    control exception.
*/

select
    vendor_payment_hk,
    vendor_payment_id,
    vendor_invoice_id,
    is_header_defect,
    header_defect_type,
    has_ap_payment_control_exception
from {{ ref('fct_vendor_payments') }}
where is_header_defect = true
  and has_ap_payment_control_exception = false
