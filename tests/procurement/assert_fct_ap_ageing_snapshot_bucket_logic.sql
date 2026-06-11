/*
    Test: AP ageing bucket matches days_past_due.

    Failure condition:
    Gold-standard ageing bucket does not align to days_past_due.
*/

select
    ap_ageing_snapshot_hk,
    snapshot_pk,
    vendor_invoice_id,
    days_past_due,
    source_ageing_bucket,
    ageing_bucket
from {{ ref('fct_ap_ageing_snapshot') }}
where (days_past_due <= 0 and ageing_bucket <> 'Current')
   or (days_past_due between 1 and 30 and ageing_bucket <> '1-30 Days Overdue')
   or (days_past_due between 31 and 60 and ageing_bucket <> '31-60 Days Overdue')
   or (days_past_due between 61 and 90 and ageing_bucket <> '61-90 Days Overdue')
   or (days_past_due >= 91 and ageing_bucket <> '91+ Days Overdue')
