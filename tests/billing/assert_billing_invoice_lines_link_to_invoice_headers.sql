/*
Purpose:
    Ensure every Billing invoice line links to a known Billing invoice header.

Grain:
    One failing row per invoice_line_id whose invoice_id is missing from
    silver.stg_billing__billing_invoices.

Expected result:
    Zero rows.
*/

with invoice_lines as (

    select
        invoice_line_id,
        invoice_id
    from {{ ref('stg_billing__billing_invoice_lines') }}

),

invoices as (

    select
        invoice_id
    from {{ ref('stg_billing__billing_invoices') }}

)

select
    invoice_lines.invoice_line_id,
    invoice_lines.invoice_id
from invoice_lines
left join invoices
    on invoice_lines.invoice_id = invoices.invoice_id
where invoices.invoice_id is null
