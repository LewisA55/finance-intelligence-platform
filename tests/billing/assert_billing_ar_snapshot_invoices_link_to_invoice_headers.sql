/*
Purpose:
    Ensure every invoice in the AR ageing snapshot links to a known Billing
    invoice header.

Grain:
    One failing row per snapshot_pk whose invoice_id is missing from
    silver.stg_billing__billing_invoices.

Expected result:
    Zero rows.
*/

with ar as (

    select
        snapshot_pk,
        snapshot_date,
        invoice_id,
        customer_id
    from {{ ref('stg_billing__ar_ageing_snapshot') }}

),

invoices as (

    select
        invoice_id
    from {{ ref('stg_billing__billing_invoices') }}

)

select
    ar.snapshot_pk,
    ar.snapshot_date,
    ar.invoice_id,
    ar.customer_id
from ar
left join invoices
    on ar.invoice_id = invoices.invoice_id
where invoices.invoice_id is null
