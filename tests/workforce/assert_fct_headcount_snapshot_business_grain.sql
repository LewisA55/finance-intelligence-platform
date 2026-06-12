select
    employee_id,
    snapshot_month_date,
    count(*) as row_count
from {{ ref('fct_headcount_snapshot') }}
group by 1, 2
having count(*) > 1
