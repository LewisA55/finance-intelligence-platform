/*
Purpose:
    Ensure every HRIS headcount snapshot employee_id links to the Silver HRIS
    employee master.

Expected result:
    Zero rows.
*/

select
    h.employee_id,
    h.snapshot_month,
    h.department_id,
    h.region_id
from {{ ref('stg_hris__hr_headcount_snapshot') }} as h
left join {{ ref('stg_hris__hr_employees') }} as e
    on h.employee_id = e.employee_id
where e.employee_id is null
