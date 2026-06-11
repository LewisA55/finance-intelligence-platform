select *
from {{ ref('fct_payroll_expense_lines') }}
where department_hk = md5('UNASSIGNED')
   or gl_account_hk = md5('UNASSIGNED_GL_ACCOUNT')
   or payroll_expense_period_date_hk = md5('UNASSIGNED')
   or period_start_date_hk = md5('UNASSIGNED')
   or period_end_date_hk = md5('UNASSIGNED')
