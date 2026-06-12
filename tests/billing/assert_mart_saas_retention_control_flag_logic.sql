select *
from {{ ref('mart_saas_retention') }}
where has_saas_retention_control_issue <> (
       arr_identity_break_event_count > 0
    or mrr_identity_break_event_count > 0
    or arr_continuity_break_count > 0
    or mrr_continuity_break_count > 0
    or negative_arr_balance_subscription_month_count > 0
    or negative_mrr_balance_subscription_month_count > 0
    or missing_subscription_master_subscription_month_count > 0
    or is_inactive_without_churn_or_pause_customer
)
