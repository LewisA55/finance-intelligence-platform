select *
from {{ ref('fct_subscription_periodic_states') }}
where reporting_month_date <> cast(date_trunc('month', reporting_month_date) as date)
