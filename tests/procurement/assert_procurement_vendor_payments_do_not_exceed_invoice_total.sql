/*
Purpose:
    Ensure clean vendor payments do not exceed clean vendor invoice gross totals.

Expected result:
    Zero rows.
*/
with payments_by_invoice as (
    select
        vendor_invoice_id,
        round(sum(payment_amount_local), 2) as payment_amount_local,
        round(sum(payment_amount_gbp), 2) as payment_amount_gbp
    from {{ ref('stg_procurement__vendor_payments') }}
    where is_defect = false
    group by vendor_invoice_id
),
clean_invoices as (
    select
        vendor_invoice_id,
        invoice_number,
        vendor_id,
        round(total_local, 2) as total_local,
        round(total_gbp, 2) as total_gbp
    from {{ ref('stg_procurement__vendor_invoices') }}
    where is_defect = false
)
select
    clean_invoices.vendor_invoice_id,
    clean_invoices.invoice_number,
    clean_invoices.vendor_id,
    clean_invoices.total_local,
    payments_by_invoice.payment_amount_local,
    round(payments_by_invoice.payment_amount_local - clean_invoices.total_local, 2) as local_overpayment,
    clean_invoices.total_gbp,
    payments_by_invoice.payment_amount_gbp,
    round(payments_by_invoice.payment_amount_gbp - clean_invoices.total_gbp, 2) as gbp_overpayment
from payments_by_invoice
inner join clean_invoices
    on payments_by_invoice.vendor_invoice_id = clean_invoices.vendor_invoice_id
where payments_by_invoice.payment_amount_local > clean_invoices.total_local + 0.01
   or payments_by_invoice.payment_amount_gbp > clean_invoices.total_gbp + 0.01
