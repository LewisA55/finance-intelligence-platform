/*
Purpose:
    Ensure every Billing payment transaction links to a known Billing customer.

Grain:
    One failing row per payment_id whose customer_id is missing from
    silver.stg_billing__billing_customers.

Expected result:
    Zero rows.
*/

with payments as (

    select
        payment_id,
        customer_id
    from {{ ref('stg_billing__billing_payments') }}

),

customers as (

    select
        customer_id
    from {{ ref('stg_billing__billing_customers') }}

)

select
    payments.payment_id,
    payments.customer_id
from payments
left join customers
    on payments.customer_id = customers.customer_id
where customers.customer_id is null
