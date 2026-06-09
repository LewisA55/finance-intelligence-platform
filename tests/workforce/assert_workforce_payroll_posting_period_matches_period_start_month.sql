/*
Purpose:
    Ensure payroll posting_period matches the month start derived from
    period_start_date.

Expected result:
    Zero rows.
*/

select
    payroll_expense_pk,
    payroll_expense_line_id,
    posting_period,
    period_start_date,
    cast(date_trunc('month', period_start_date) as date) as expected_posting_period
from {{ ref('stg_workforce__payroll_expense_lines') }}
where posting_period != cast(date_trunc('month', period_start_date) as date)
