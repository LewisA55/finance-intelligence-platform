/*
    Test: fct_billing_payments positive cash receipt amounts.

    Failure condition:
    Any payment where local or GBP payment amount is null, zero, or negative.

    The Silver payment source represents realised customer remittance events.
    Refunds, chargebacks, or reversals would require explicit source-system
    transaction types before being modelled as negative payment events.
*/

select
    payment_id,
    payment_status,
    payment_method,
    currency_code,
    payment_amount_local,
    payment_amount_gbp
from {{ ref('fct_billing_payments') }}
where
    payment_amount_local is null
    or payment_amount_gbp is null
    or payment_amount_local <= 0
    or payment_amount_gbp <= 0
