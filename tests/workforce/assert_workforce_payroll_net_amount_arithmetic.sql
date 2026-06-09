/*
Purpose:
    Ensure payroll actuals net amount fields equal debit minus credit values.

Expected result:
    Zero rows.
*/

select
    payroll_expense_pk,
    payroll_expense_line_id,
    debit_local,
    credit_local,
    net_amount_local,
    debit_gbp,
    credit_gbp,
    net_amount_gbp
from {{ ref('stg_workforce__payroll_expense_lines') }}
where abs(net_amount_local - (debit_local - credit_local)) > 0.01
   or abs(net_amount_gbp - (debit_gbp - credit_gbp)) > 0.01
