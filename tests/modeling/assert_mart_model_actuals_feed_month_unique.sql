select
    reporting_month_date,
    reporting_scope,
    scenario_code,
    count(*) as row_count
from {{ ref('mart_model_actuals_feed') }}
group by 1, 2, 3
having count(*) <> 1
