/*
Purpose:
    Ensure every workforce employee compensation line links to the Silver HRIS
    employee master.

Expected result:
    Zero rows.
*/

select
    c.compensation_pk,
    c.compensation_line_id,
    c.employee_id,
    c.posting_period,
    c.compensation_component
from {{ ref('stg_workforce__employee_compensation') }} as c
left join {{ ref('stg_hris__hr_employees') }} as e
    on c.employee_id = e.employee_id
where e.employee_id is null
