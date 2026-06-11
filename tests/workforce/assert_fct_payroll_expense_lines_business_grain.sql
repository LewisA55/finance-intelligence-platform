select
    payroll_expense_period_date,
    department_id,
    account_code,
    currency_code,
    cost_component,
    count(*) as row_count
from {{ ref('fct_payroll_expense_lines') }}
group by 1, 2, 3, 4, 5
having count(*) > 1
