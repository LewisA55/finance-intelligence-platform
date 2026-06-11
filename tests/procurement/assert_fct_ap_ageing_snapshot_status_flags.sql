/*
    Test: AP ageing status flags are consistent with days_past_due.

    Failure condition:
    Current/overdue flags do not agree to days_past_due.
*/

select
    ap_ageing_snapshot_hk,
    snapshot_pk,
    vendor_invoice_id,
    days_past_due,
    is_current,
    is_overdue,
    is_1_30_overdue,
    is_31_60_overdue,
    is_61_90_overdue,
    is_91_plus_overdue
from {{ ref('fct_ap_ageing_snapshot') }}
where (days_past_due <= 0 and (is_current = false or is_overdue = true))
   or (days_past_due > 0 and (is_current = true or is_overdue = false))
   or (days_past_due between 1 and 30 and is_1_30_overdue = false)
   or (days_past_due between 31 and 60 and is_31_60_overdue = false)
   or (days_past_due between 61 and 90 and is_61_90_overdue = false)
   or (days_past_due >= 91 and is_91_plus_overdue = false)
