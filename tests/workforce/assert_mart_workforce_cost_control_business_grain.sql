select
    department_hk,
    reporting_month_date_hk,
    count(*) as row_count
from {{ ref('mart_workforce_cost_control') }}
group by 1, 2
having count(*) > 1
