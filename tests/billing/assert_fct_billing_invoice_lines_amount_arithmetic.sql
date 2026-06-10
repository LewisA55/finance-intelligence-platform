/*
    Test: fct_billing_invoice_lines amount arithmetic.

    Failure condition:
    Any invoice line where quantity * unit price does not equal line amount
    within a 0.01 tolerance in either local currency or GBP.
*/

select
    invoice_line_id,
    invoice_id,
    quantity,
    unit_price_local,
    line_amount_local,
    unit_price_gbp,
    line_amount_gbp
from {{ ref('fct_billing_invoice_lines') }}
where
    abs(
        round(coalesce(quantity, 0) * coalesce(unit_price_local, 0), 2)
        - round(coalesce(line_amount_local, 0), 2)
    ) > 0.01
    or
    abs(
        round(coalesce(quantity, 0) * coalesce(unit_price_gbp, 0), 2)
        - round(coalesce(line_amount_gbp, 0), 2)
    ) > 0.01
