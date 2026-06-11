select *
from {{ ref('fct_employee_compensation') }}
where employee_hk = md5('UNASSIGNED')
   or department_hk = md5('UNASSIGNED')
   or region_hk = md5('UNASSIGNED')
   or compensation_period_date_hk = md5('UNASSIGNED')
   or period_start_date_hk = md5('UNASSIGNED')
   or period_end_date_hk = md5('UNASSIGNED')
