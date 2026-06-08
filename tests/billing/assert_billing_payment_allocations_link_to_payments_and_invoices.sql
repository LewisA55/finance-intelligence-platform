/*
Purpose:
    Ensure every payment allocation links to both a known payment transaction
    and a known invoice header.

Grain:
    One failing row per allocation_id with a missing payment_id or invoice_id
    relationship.

Expected result:
    Zero rows.
*/

with allocations as (

    select
        allocation_id,
        payment_id,
        invoice_id,
        customer_id
    from {{ ref('stg_billing__billing_payment_allocations') }}

),

payments as (

    select
        payment_id
    from {{ ref('stg_billing__billing_payments') }}

),

invoices as (

    select
        invoice_id
    from {{ ref('stg_billing__billing_invoices') }}

)

select
    allocations.allocation_id,
    allocations.payment_id,
    allocations.invoice_id,
    allocations.customer_id,
    case when payments.payment_id is null then true else false end as missing_payment,
    case when invoices.invoice_id is null then true else false end as missing_invoice
from allocations
left join payments
    on allocations.payment_id = payments.payment_id
left join invoices
    on allocations.invoice_id = invoices.invoice_id
where
    payments.payment_id is null
    or invoices.invoice_id is null
