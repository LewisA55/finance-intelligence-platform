select
    subscription_id,
    reporting_month_date,
    count(*) as row_count
from {{ ref('fct_subscription_periodic_states') }}
group by 1, 2
having count(*) > 1
