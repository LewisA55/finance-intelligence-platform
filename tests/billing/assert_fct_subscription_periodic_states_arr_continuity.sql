select *
from {{ ref('fct_subscription_periodic_states') }}
where has_arr_continuity_break
   or arr_continuity_variance_gbp <> 0
