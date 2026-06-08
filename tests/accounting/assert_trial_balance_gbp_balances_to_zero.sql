/*
Project Atlas / Finance Intelligence Platform
Singular dbt test: Trial Balance GBP zero-balance control

Purpose
-------
Validates the core Trial Balance accounting invariant:

    For each posting_period:
        SUM(closing_balance_gbp) = 0.00

The Trial Balance stores balances using universal algebraic signs:
- Assets / Expenses are normally debit-positive
- Liabilities / Equity / Revenue are normally credit-negative

Therefore, a balanced Trial Balance should net to zero at each posting period
when evaluated in GBP.

Failure behaviour
-----------------
This test returns one row per posting period where the absolute GBP imbalance
exceeds the configured tolerance. In dbt, any returned row means the test fails.
*/

{{ config(
    severity='error',
    tags=['accounting_control', 'trial_balance', 'financial_invariant']
) }}

with period_balances as (

    select
        posting_period,
        round(sum(closing_balance_gbp), 4) as closing_balance_gbp_net
    from {{ ref('stg_accounting__trial_balance') }}
    group by posting_period

),

failures as (

    select
        posting_period,
        closing_balance_gbp_net
    from period_balances
    where abs(closing_balance_gbp_net) > 0.01

)

select *
from failures
