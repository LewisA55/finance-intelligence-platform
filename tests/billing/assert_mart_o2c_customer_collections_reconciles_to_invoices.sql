/*
    Test: mart_o2c_customer_collections reconciles to fct_billing_invoices.

    Failure condition:
    Total billed GBP in the customer-month mart differs from the locked invoice
    fact by more than 0.01.
*/

with mart as (

    select round(sum(billed_amount_gbp), 2) as billed_amount_gbp
    from {{ ref('mart_o2c_customer_collections') }}

),

fact as (

    select round(sum(total_billed_amount_gbp), 2) as billed_amount_gbp
    from {{ ref('fct_billing_invoices') }}

)

select
    mart.billed_amount_gbp as mart_billed_amount_gbp,
    fact.billed_amount_gbp as fact_billed_amount_gbp,
    round(mart.billed_amount_gbp - fact.billed_amount_gbp, 2) as variance_gbp
from mart
cross join fact
where abs(round(mart.billed_amount_gbp - fact.billed_amount_gbp, 2)) > 0.01
