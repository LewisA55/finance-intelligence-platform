/*
    Test: AP ageing snapshot contains positive open AP exposures.

    Failure condition:
    A snapshot row has an open amount less than or equal to zero.
*/

select
    ap_ageing_snapshot_hk,
    snapshot_pk,
    vendor_invoice_id,
    open_amount_gbp,
    is_open_ap_exposure
from {{ ref('fct_ap_ageing_snapshot') }}
where open_amount_gbp <= 0
   or is_open_ap_exposure = false
