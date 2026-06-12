select *
from {{ ref('fct_subscription_periodic_states') }}
where
    (is_churned_subscription_month and is_paused_subscription_month)
    or (is_active_subscription_month and (is_churned_subscription_month or is_paused_subscription_month))
    or (not is_active_subscription_month and active_arr_gbp <> 0)
    or (not is_active_subscription_month and active_mrr_gbp <> 0)
    or (has_subscription_event <> (event_count > 0))
    or (has_terminal_event <> (terminal_event_count > 0))
