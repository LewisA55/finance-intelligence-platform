select *
from {{ ref('fct_subscription_events') }}
where
    (event_type in ('New', 'Expansion', 'Price Increase') and arr_delta_gbp < 0)
    or (event_type in ('Contraction', 'Churn', 'Pause') and arr_delta_gbp > 0)
    or (event_type = 'Renewal' and mrr_delta_gbp <> 0)
