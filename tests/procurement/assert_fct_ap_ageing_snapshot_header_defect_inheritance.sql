/*
    Test: fct_ap_ageing_snapshot inherits parent invoice defect flags.

    Failure condition:
    A row attached to a defective invoice is not marked with an AP ageing
    control exception.
*/

select
    ap_ageing_snapshot_hk,
    snapshot_pk,
    vendor_invoice_id,
    is_header_defect,
    header_defect_type,
    has_ap_ageing_control_exception
from {{ ref('fct_ap_ageing_snapshot') }}
where is_header_defect = true
  and has_ap_ageing_control_exception = false
