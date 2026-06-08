/*
Purpose:
    Ensure every Billing invoice header links to a known Billing customer.

Grain:
    One failing row per invoice_id whose customer_id is missing from
    silver.stg_billing__billing_customers.

Expected result:
    Zero rows.
*/

with invoices as (

    select
        invoice_id,
        customer_id
    from {{ ref('stg_billing__billing_invoices') }}

),

customers as (

    select
        customer_id
    from {{ ref('stg_billing__billing_customers') }}

)

select
    invoices.invoice_id,
    invoices.customer_id
from invoices
left join customers
    on invoices.customer_id = customers.customer_id
where customers.customer_id is null
