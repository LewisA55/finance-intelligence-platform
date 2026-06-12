select *
from {{ ref('fct_headcount_plan') }}
where
    (plan_status = 'ACTIVE' and (employee_id is null or trim(employee_id) = ''))
    or (plan_status in ('OPEN_BUDGETED', 'BACKFILL') and employee_id is not null and trim(employee_id) <> '')
    or (employee_id is not null and trim(employee_id) <> '' and employee_hk = md5('UNASSIGNED'))
    or ((employee_id is null or trim(employee_id) = '') and employee_hk <> md5('UNASSIGNED'))
