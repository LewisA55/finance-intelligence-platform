select *
from {{ ref('fct_payroll_expense_lines') }}
where round(debit_gbp - credit_gbp - net_amount_gbp, 2) <> 0
   or round(debit_local - credit_local - net_amount_local, 2) <> 0
