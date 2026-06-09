/*
Purpose:
    Ensure every clean AP ageing snapshot row links to a known clean vendor invoice header.
Expected result:
    Zero rows.
*/
with ageing as (
    select snapshot_pk, snapshot_date, vendor_invoice_id, vendor_id, vendor_name, invoice_number, open_amount_gbp
    from {{ ref('stg_procurement__ap_ageing_snapshot') }}
    where is_defect = false
),
invoices as (
    select vendor_invoice_id
    from {{ ref('stg_procurement__vendor_invoices') }}
    where is_defect = false
)
select
    ageing.snapshot_pk,
    ageing.snapshot_date,
    ageing.vendor_invoice_id,
    ageing.vendor_id,
    ageing.vendor_name,
    ageing.invoice_number,
    ageing.open_amount_gbp
from ageing
left join invoices
    on ageing.vendor_invoice_id = invoices.vendor_invoice_id
where invoices.vendor_invoice_id is null
