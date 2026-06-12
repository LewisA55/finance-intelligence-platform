select *
from {{ ref('fct_subscription_events') }}
where has_mrr_identity_break
