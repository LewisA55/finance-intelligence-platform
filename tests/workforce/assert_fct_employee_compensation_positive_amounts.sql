select *
from {{ ref('fct_employee_compensation') }}
where amount_local <= 0
   or amount_gbp <= 0
   or annual_base_salary_local <= 0
   or monthly_base_salary_local <= 0
