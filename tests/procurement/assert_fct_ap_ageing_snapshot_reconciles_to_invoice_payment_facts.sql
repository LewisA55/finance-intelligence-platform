/*
    Test: AP ageing open exposure reconciles to vendor invoices less vendor payments.

    Failure condition:
    AP ageing open amount does not agree to calculated invoice exposure.
*/

select
    ap_ageing_snapshot_hk,
    snapshot_pk,
    vendor_invoice_id,
    open_amount_gbp,
    calculated_open_amount_gbp,
    open_amount_reconciliation_variance_gbp,
    paid_amount_gbp,
    calculated_paid_amount_gbp,
    paid_amount_reconciliation_variance_gbp
from {{ ref('fct_ap_ageing_snapshot') }}
where abs(open_amount_reconciliation_variance_local) > 0.01
   or abs(open_amount_reconciliation_variance_gbp) > 0.01
   or abs(paid_amount_reconciliation_variance_local) > 0.01
   or abs(paid_amount_reconciliation_variance_gbp) > 0.01
