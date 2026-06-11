select *
from {{ ref('fct_payroll_expense_lines') }}
where employee_count <= 0
   or debit_local <= 0
   or debit_gbp <= 0
   or net_amount_local <= 0
   or net_amount_gbp <= 0
   or credit_local < 0
   or credit_gbp < 0
