/*
    Test: AP ageing source open amount arithmetic is valid.

    Failure condition:
    invoice_total - paid_amount - open_amount does not equal zero.
*/

select
    ap_ageing_snapshot_hk,
    snapshot_pk,
    vendor_invoice_id,
    invoice_total_gbp,
    paid_amount_gbp,
    open_amount_gbp,
    source_open_amount_arithmetic_variance_gbp
from {{ ref('fct_ap_ageing_snapshot') }}
where abs(source_open_amount_arithmetic_variance_local) > 0.01
   or abs(source_open_amount_arithmetic_variance_gbp) > 0.01
