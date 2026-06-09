/*
Purpose:
    Ensure every clean AP ageing snapshot row links to a known clean vendor master record.
Expected result:
    Zero rows.
*/
with ageing as (
    select snapshot_pk, snapshot_date, vendor_invoice_id, vendor_id, vendor_name, open_amount_gbp
    from {{ ref('stg_procurement__ap_ageing_snapshot') }}
    where is_defect = false
),
vendors as (
    select vendor_id
    from {{ ref('stg_procurement__vendors') }}
    where is_defect = false
)
select
    ageing.snapshot_pk,
    ageing.snapshot_date,
    ageing.vendor_invoice_id,
    ageing.vendor_id,
    ageing.vendor_name,
    ageing.open_amount_gbp
from ageing
left join vendors
    on ageing.vendor_id = vendors.vendor_id
where vendors.vendor_id is null
