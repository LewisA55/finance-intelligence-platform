/*
Purpose:
    Reconcile AR ageing open amount to invoice total less paid amount.

Grain:
    One failing row per AR ageing snapshot row.

Expected result:
    Zero rows.

Notes:
    This validates the arithmetic of the AR snapshot itself, including negative
    open balances for overpaid invoices.
*/

select
    snapshot_pk,
    snapshot_date,
    invoice_id,
    customer_id,
    invoice_total_local,
    paid_amount_local,
    open_amount_local,
    round(invoice_total_local - paid_amount_local, 2) as expected_open_amount_local,
    invoice_total_gbp,
    paid_amount_gbp,
    open_amount_gbp,
    round(invoice_total_gbp - paid_amount_gbp, 2) as expected_open_amount_gbp,
    round(open_amount_local - (invoice_total_local - paid_amount_local), 2) as local_variance,
    round(open_amount_gbp - (invoice_total_gbp - paid_amount_gbp), 2) as gbp_variance
from {{ ref('stg_billing__ar_ageing_snapshot') }}
where
    abs(open_amount_local - (invoice_total_local - paid_amount_local)) > 0.01
    or abs(open_amount_gbp - (invoice_total_gbp - paid_amount_gbp)) > 0.01
