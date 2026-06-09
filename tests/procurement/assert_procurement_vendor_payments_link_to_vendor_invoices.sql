/*
Purpose:
    Ensure every clean vendor payment references a known clean vendor invoice.
Expected result:
    Zero rows.
*/
with payments as (
    select vendor_payment_id, vendor_invoice_id, vendor_id, vendor_name, invoice_number, payment_amount_gbp
    from {{ ref('stg_procurement__vendor_payments') }}
    where is_defect = false
),
invoices as (
    select vendor_invoice_id
    from {{ ref('stg_procurement__vendor_invoices') }}
    where is_defect = false
)
select
    payments.vendor_payment_id,
    payments.vendor_invoice_id,
    payments.vendor_id,
    payments.vendor_name,
    payments.invoice_number,
    payments.payment_amount_gbp
from payments
left join invoices
    on payments.vendor_invoice_id = invoices.vendor_invoice_id
where invoices.vendor_invoice_id is null
