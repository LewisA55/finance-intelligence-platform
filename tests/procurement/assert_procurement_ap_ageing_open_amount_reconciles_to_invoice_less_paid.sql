/*
Purpose:
    Validate clean AP ageing arithmetic.

Formula:
    invoice total - paid amount = open amount

Expected result:
    Zero rows.
*/
select
    snapshot_pk,
    snapshot_date,
    vendor_invoice_id,
    vendor_id,
    vendor_name,
    invoice_number,
    invoice_total_local,
    paid_amount_local,
    open_amount_local,
    round(invoice_total_local - paid_amount_local - open_amount_local, 2) as local_variance,
    invoice_total_gbp,
    paid_amount_gbp,
    open_amount_gbp,
    round(invoice_total_gbp - paid_amount_gbp - open_amount_gbp, 2) as gbp_variance
from {{ ref('stg_procurement__ap_ageing_snapshot') }}
where is_defect = false
  and (
      abs(invoice_total_local - paid_amount_local - open_amount_local) > 0.01
      or abs(invoice_total_gbp - paid_amount_gbp - open_amount_gbp) > 0.01
  )
