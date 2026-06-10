/*
    Test: fct_gl_actuals journals balance to zero in GBP.

    Grain checked:
    journal_id

    Failure condition:
    Any journal where total debits GBP minus total credits GBP does not net to
    zero within a 0.01 tolerance.

    This protects the atomic double-entry integrity of gold.fct_gl_actuals.
*/

select
    journal_id,
    round(sum(coalesce(debit_amount_gbp, 0)), 2) as total_debits_gbp,
    round(sum(coalesce(credit_amount_gbp, 0)), 2) as total_credits_gbp,
    round(sum(coalesce(net_amount_gbp, 0)), 2) as net_amount_gbp,
    count(*) as journal_line_count
from {{ ref('fct_gl_actuals') }}
group by journal_id
having abs(round(sum(coalesce(net_amount_gbp, 0)), 2)) > 0.01
