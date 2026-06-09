/*
Purpose:
    Ensure ACTIVE headcount plan rows with assigned employees link to the Silver
    HRIS employee master.

Expected result:
    Zero rows.
*/

select
    p.position_pk,
    p.position_id,
    p.employee_id,
    p.plan_status,
    p.department_id,
    p.region_id
from {{ ref('stg_workforce__headcount_plan') }} as p
left join {{ ref('stg_hris__hr_employees') }} as e
    on p.employee_id = e.employee_id
where p.plan_status = 'ACTIVE'
  and e.employee_id is null
