/*
    Test: mart_o2c_customer_collections reconciles to fct_billing_payment_allocations.

    Failure condition:
    Total allocated GBP in the customer-month mart differs from the locked
    allocation fact by more than 0.01.
*/

with mart as (

    select round(sum(allocated_amount_gbp), 2) as allocated_amount_gbp
    from {{ ref('mart_o2c_customer_collections') }}

),

fact as (

    select round(sum(allocated_amount_gbp), 2) as allocated_amount_gbp
    from {{ ref('fct_billing_payment_allocations') }}

)

select
    mart.allocated_amount_gbp as mart_allocated_amount_gbp,
    fact.allocated_amount_gbp as fact_allocated_amount_gbp,
    round(mart.allocated_amount_gbp - fact.allocated_amount_gbp, 2) as variance_gbp
from mart
cross join fact
where abs(round(mart.allocated_amount_gbp - fact.allocated_amount_gbp, 2)) > 0.01
