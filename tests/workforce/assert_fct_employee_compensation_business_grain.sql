select
    employee_id,
    compensation_period_date,
    compensation_component,
    count(*) as row_count
from {{ ref('fct_employee_compensation') }}
group by 1, 2, 3
having count(*) > 1
