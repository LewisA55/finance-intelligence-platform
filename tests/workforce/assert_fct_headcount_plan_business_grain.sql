select
    position_id,
    count(*) as row_count
from {{ ref('fct_headcount_plan') }}
group by 1
having count(*) > 1
