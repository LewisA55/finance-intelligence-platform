/*
Purpose:
    Ensure every clean revenue recognition schedule row either links to a clean
    Billing invoice line or is outside clean scope because its related Billing
    document is intentionally defect-flagged.

Expected result:
    Zero rows.
*/

with recognition as (

    select
        revenue_recognition_pk,
        recognition_id,
        invoice_id,
        invoice_line_id,
        customer_id,
        subscription_id,
        product_id
    from {{ ref('stg_revenue__revenue_recognition_schedule') }}
    where is_defect = false

),

invoices as (

    select
        invoice_id,
        is_defect as invoice_is_defect
    from {{ ref('stg_billing__billing_invoices') }}

),

invoice_lines as (

    select
        invoice_line_id,
        invoice_id,
        is_defect as line_is_defect
    from {{ ref('stg_billing__billing_invoice_lines') }}

)

select
    recognition.revenue_recognition_pk,
    recognition.recognition_id,
    recognition.invoice_id,
    recognition.invoice_line_id,
    recognition.customer_id,
    recognition.subscription_id,
    recognition.product_id
from recognition
left join invoices
    on recognition.invoice_id = invoices.invoice_id
left join invoice_lines
    on recognition.invoice_line_id = invoice_lines.invoice_line_id
where
    (
        invoices.invoice_id is null
        or invoice_lines.invoice_line_id is null
    )
    and coalesce(invoices.invoice_is_defect, false) = false
    and coalesce(invoice_lines.line_is_defect, false) = false