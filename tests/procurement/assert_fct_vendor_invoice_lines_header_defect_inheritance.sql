/*
    Test: fct_vendor_invoice_lines inherit parent invoice defect flags.

    Failure condition:
    A line attached to a defective invoice is not marked with an AP control exception.
*/

select
    vendor_invoice_line_hk,
    vendor_invoice_line_id,
    vendor_invoice_id,
    is_header_defect,
    header_defect_type,
    has_ap_control_exception
from {{ ref('fct_vendor_invoice_lines') }}
where is_header_defect = true
  and has_ap_control_exception = false
