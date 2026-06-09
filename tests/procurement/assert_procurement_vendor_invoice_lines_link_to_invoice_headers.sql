/*
Purpose:
    Ensure every clean vendor invoice line links to a known clean vendor invoice header.
Expected result:
    Zero rows.
*/
with invoice_lines as (
    select vendor_invoice_line_id, vendor_invoice_id, vendor_id, vendor_name, account_code, line_amount_gbp
    from {{ ref('stg_procurement__vendor_invoice_lines') }}
    where is_defect = false
),
invoice_headers as (
    select vendor_invoice_id
    from {{ ref('stg_procurement__vendor_invoices') }}
    where is_defect = false
)
select
    invoice_lines.vendor_invoice_line_id,
    invoice_lines.vendor_invoice_id,
    invoice_lines.vendor_id,
    invoice_lines.vendor_name,
    invoice_lines.account_code,
    invoice_lines.line_amount_gbp
from invoice_lines
left join invoice_headers
    on invoice_lines.vendor_invoice_id = invoice_headers.vendor_invoice_id
where invoice_headers.vendor_invoice_id is null
