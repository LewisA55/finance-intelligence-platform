/*
Purpose:
    Ensure every clean vendor invoice header links to a known clean vendor master record.
Expected result:
    Zero rows.
*/
with invoices as (
    select vendor_invoice_id, vendor_id, vendor_name, invoice_number
    from {{ ref('stg_procurement__vendor_invoices') }}
    where is_defect = false
),
vendors as (
    select vendor_id
    from {{ ref('stg_procurement__vendors') }}
    where is_defect = false
)
select
    invoices.vendor_invoice_id,
    invoices.vendor_id,
    invoices.vendor_name,
    invoices.invoice_number
from invoices
left join vendors
    on invoices.vendor_id = vendors.vendor_id
where vendors.vendor_id is null
