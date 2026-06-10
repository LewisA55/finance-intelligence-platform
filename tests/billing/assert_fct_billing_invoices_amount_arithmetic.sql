/*
    Test: fct_billing_invoices amount arithmetic.

    Failure condition:
    Any invoice where subtotal + tax does not equal total billed amount within
    a 0.01 tolerance in either local currency or GBP.

    Controlled tax defects are already reflected in the source amount fields,
    so this test validates internal document arithmetic rather than whether the
    tax rate itself is commercially correct.
*/

select
    invoice_id,
    subtotal_amount_local,
    tax_amount_local,
    total_billed_amount_local,
    subtotal_amount_gbp,
    tax_amount_gbp,
    total_billed_amount_gbp
from {{ ref('fct_billing_invoices') }}
where
    abs(
        round(coalesce(subtotal_amount_local, 0) + coalesce(tax_amount_local, 0), 2)
        - round(coalesce(total_billed_amount_local, 0), 2)
    ) > 0.01
    or
    abs(
        round(coalesce(subtotal_amount_gbp, 0) + coalesce(tax_amount_gbp, 0), 2)
        - round(coalesce(total_billed_amount_gbp, 0), 2)
    ) > 0.01
