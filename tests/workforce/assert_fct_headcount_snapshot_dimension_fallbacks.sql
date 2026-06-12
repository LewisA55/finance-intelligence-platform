select *
from {{ ref('fct_headcount_snapshot') }}
where employee_hk = md5('UNASSIGNED')
   or department_hk = md5('UNASSIGNED')
   or region_hk = md5('UNASSIGNED')
   or snapshot_month_date_hk = md5('UNASSIGNED')
