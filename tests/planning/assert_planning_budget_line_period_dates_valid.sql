/*
Purpose:
    Ensure budget line period dates are chronologically valid and posting period equals the month start derived from period_start_date.

Expected result:
    Zero rows.
*/

select
    budget_line_pk,
    budget_line_id,
    posting_period,
    period_start_date,
    period_end_date,
    cast(date_trunc('month', period_start_date) as date) as expected_posting_period
from {{ ref('stg_planning__budget_lines') }}
where period_start_date > period_end_date
   or posting_period != cast(date_trunc('month', period_start_date) as date)
