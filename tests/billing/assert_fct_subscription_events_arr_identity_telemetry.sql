select *
from {{ ref('fct_subscription_events') }}
where has_arr_identity_break <> (arr_identity_variance_gbp <> 0)
   or has_mrr_identity_break <> (mrr_identity_variance_gbp <> 0)
