/*
    Test: fct_ap_ageing_snapshot business grain is unique.

    Failure condition:
    More than one row exists for the same vendor invoice and snapshot date.
*/

select
    snapshot_date_hk,
    snapshot_date,
    vendor_invoice_hk,
    vendor_invoice_id,
    count(*) as row_count
from {{ ref('fct_ap_ageing_snapshot') }}
group by
    snapshot_date_hk,
    snapshot_date,
    vendor_invoice_hk,
    vendor_invoice_id
having count(*) > 1
