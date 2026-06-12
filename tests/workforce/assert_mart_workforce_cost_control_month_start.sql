select *
from {{ ref('mart_workforce_cost_control') }}
where reporting_month_date <> cast(date_trunc('month', reporting_month_date) as date)
