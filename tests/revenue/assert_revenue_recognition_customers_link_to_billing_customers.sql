/*
Purpose:
    Ensure every clean revenue recognition schedule row links to a known Billing
    customer.

Grain:
    One failing row per clean revenue recognition row whose customer_id is
    missing from silver.stg_billing__billing_customers.

Expected result:
    Zero rows.
*/

with recognition as (

    select
        revenue_recognition_pk,
        recognition_id,
        invoice_id,
        customer_id
    from {{ ref('stg_revenue__revenue_recognition_schedule') }}
    where is_defect = false

),

customers as (

    select
        customer_id
    from {{ ref('stg_billing__billing_customers') }}

)

select
    recognition.revenue_recognition_pk,
    recognition.recognition_id,
    recognition.invoice_id,
    recognition.customer_id
from recognition
left join customers
    on recognition.customer_id = customers.customer_id
where customers.customer_id is null
