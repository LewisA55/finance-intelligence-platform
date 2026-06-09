/*
Purpose:
    Ensure every clean vendor payment links to a known clean vendor master record.
Expected result:
    Zero rows.
*/
with payments as (
    select vendor_payment_id, vendor_invoice_id, vendor_id, vendor_name, payment_amount_gbp
    from {{ ref('stg_procurement__vendor_payments') }}
    where is_defect = false
),
vendors as (
    select vendor_id
    from {{ ref('stg_procurement__vendors') }}
    where is_defect = false
)
select
    payments.vendor_payment_id,
    payments.vendor_invoice_id,
    payments.vendor_id,
    payments.vendor_name,
    payments.payment_amount_gbp
from payments
left join vendors
    on payments.vendor_id = vendors.vendor_id
where vendors.vendor_id is null
