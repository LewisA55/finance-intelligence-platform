/*
Purpose:
    Ensure payroll expense period dates are chronologically valid.

Expected result:
    Zero rows.
*/

select
    payroll_expense_pk,
    payroll_expense_line_id,
    posting_period,
    period_start_date,
    period_end_date
from {{ ref('stg_workforce__payroll_expense_lines') }}
where period_start_date > period_end_date
