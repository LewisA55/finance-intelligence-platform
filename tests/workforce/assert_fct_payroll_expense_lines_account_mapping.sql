select *
from {{ ref('fct_payroll_expense_lines') }}
where account_code <> '6100'
   or not is_payroll_expense_account
   or not is_expense_account
   or gl_account_hk = md5('UNASSIGNED_GL_ACCOUNT')
