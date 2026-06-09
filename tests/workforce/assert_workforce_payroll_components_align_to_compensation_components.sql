/*
Purpose:
    Ensure clean payroll actuals use cost components that exist in the workforce
    employee compensation source.

Expected result:
    Zero rows.
*/

with compensation_components as (

    select distinct
        compensation_component as component_code
    from {{ ref('stg_workforce__employee_compensation') }}
    where is_defect = false

),

payroll_components as (

    select distinct
        cost_component as component_code
    from {{ ref('stg_workforce__payroll_expense_lines') }}
    where is_defect = false

)

select
    p.component_code
from payroll_components as p
left join compensation_components as c
    on p.component_code = c.component_code
where c.component_code is null
