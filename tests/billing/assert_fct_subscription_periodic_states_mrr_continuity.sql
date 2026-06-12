select *
from {{ ref('fct_subscription_periodic_states') }}
where has_mrr_continuity_break
   or mrr_continuity_variance_gbp <> 0
