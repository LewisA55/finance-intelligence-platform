select
    subscription_id,
    event_sequence,
    count(*) as row_count
from {{ ref('fct_subscription_events') }}
group by 1, 2
having count(*) > 1
