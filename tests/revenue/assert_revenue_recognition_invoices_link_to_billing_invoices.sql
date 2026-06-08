/*
Purpose:
    Ensure every clean revenue recognition schedule row links to a known clean
    Billing invoice header, excluding recognition rows attached to intentionally
    defect-flagged Billing documents.

Expected result:
    Zero rows.
*/

with recognition as (

    select
        revenue_recognition_pk,
        recognition_id,
        invoice_id,
        invoice_line_id,
        customer_id
    from {{ ref('stg_revenue__revenue_recognition_schedule') }}
    where is_defect = false

),

invoices as (

    select
        invoice_id,
        is_defect as invoice_is_defect
    from {{ ref('stg_billing__billing_invoices') }}

)

select
    recognition.revenue_recognition_pk,
    recognition.recognition_id,
    recognition.invoice_id,
    recognition.invoice_line_id,
    recognition.customer_id
from recognition
left join invoices
    on recognition.invoice_id = invoices.invoice_id
where
    invoices.invoice_id is null