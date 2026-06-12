select *
from {{ ref('fct_subscription_periodic_states') }}
where reporting_month_date_hk = md5('UNASSIGNED')
   or customer_hk = md5('UNASSIGNED')
   or region_hk = md5('UNASSIGNED')
