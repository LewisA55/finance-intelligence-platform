/*
Purpose:
    Ensure payroll expense account_code values link to the Silver chart of
    accounts.

Expected result:
    Zero rows.
*/

select
    p.payroll_expense_pk,
    p.payroll_expense_line_id,
    p.posting_period,
    p.department_id,
    p.account_code,
    p.account_name
from {{ ref('stg_workforce__payroll_expense_lines') }} as p
left join {{ ref('stg_accounting__chart_of_accounts') }} as coa
    on p.account_code = coa.account_code
where coa.account_code is null
