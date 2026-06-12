select *
from {{ ref('fct_subscription_events') }}
where event_date_hk = md5('UNASSIGNED')
   or customer_hk = md5('UNASSIGNED')
   or region_hk = md5('UNASSIGNED')
