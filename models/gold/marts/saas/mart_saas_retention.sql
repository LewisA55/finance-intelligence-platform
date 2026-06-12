{{ config(
    materialized = 'table',
    schema = 'gold'
) }}

with states as (

    select *
    from {{ ref('fct_subscription_periodic_states') }}

),

customer_month as (

    select
        states.reporting_month_date_hk,
        states.reporting_month_date,
        states.customer_hk,
        states.region_hk,
        coalesce(states.customer_segment, 'Unknown') as customer_segment,

        count(distinct states.subscription_id) as subscription_count,

        sum(states.beginning_arr_gbp) as beginning_arr_gbp,
        sum(states.ending_arr_gbp) as ending_arr_gbp,
        sum(states.active_arr_gbp) as ending_active_arr_gbp,
        sum(states.paused_arr_balance_gbp) as paused_arr_balance_gbp,

        sum(states.beginning_mrr_gbp) as beginning_mrr_gbp,
        sum(states.ending_mrr_gbp) as ending_mrr_gbp,
        sum(states.active_mrr_gbp) as ending_active_mrr_gbp,

        sum(states.new_business_arr_gbp) as new_business_arr_gbp,
        sum(states.expansion_arr_gbp) as expansion_arr_gbp,
        sum(states.price_increase_arr_gbp) as price_increase_arr_gbp,
        sum(states.gross_expansion_arr_gbp) as gross_expansion_arr_gbp,
        sum(states.contraction_arr_gbp) as contraction_arr_gbp,
        sum(states.churn_arr_gbp) as churn_arr_gbp,
        sum(states.pause_arr_gbp) as pause_arr_gbp,
        sum(states.renewal_arr_delta_gbp) as renewal_arr_delta_gbp,
        sum(states.net_arr_delta_gbp) as net_arr_delta_gbp,

        sum(states.event_count) as event_count,
        sum(states.new_event_count) as new_event_count,
        sum(states.renewal_event_count) as renewal_event_count,
        sum(states.expansion_event_count) as expansion_event_count,
        sum(states.price_increase_event_count) as price_increase_event_count,
        sum(states.contraction_event_count) as contraction_event_count,
        sum(states.churn_event_count) as churn_event_count,
        sum(states.pause_event_count) as pause_event_count,

        sum(case when states.is_active_subscription_month then 1 else 0 end) as active_subscription_count,
        sum(case when states.is_paused_subscription_month then 1 else 0 end) as paused_subscription_count,
        sum(case when states.is_churned_subscription_month then 1 else 0 end) as churned_subscription_count,

        sum(states.arr_identity_break_event_count) as arr_identity_break_event_count,
        sum(states.mrr_identity_break_event_count) as mrr_identity_break_event_count,
        sum(case when states.has_arr_continuity_break then 1 else 0 end) as arr_continuity_break_count,
        sum(case when states.has_mrr_continuity_break then 1 else 0 end) as mrr_continuity_break_count,
        sum(case when states.has_negative_arr_balance then 1 else 0 end) as negative_arr_balance_subscription_month_count,
        sum(case when states.has_negative_mrr_balance then 1 else 0 end) as negative_mrr_balance_subscription_month_count,
        sum(case when states.has_missing_subscription_master then 1 else 0 end) as missing_subscription_master_subscription_month_count,

        sum(states.arr_identity_variance_gbp) as arr_identity_variance_gbp,
        sum(states.mrr_identity_variance_gbp) as mrr_identity_variance_gbp

    from states
    group by 1, 2, 3, 4, 5

),

customer_flags as (

    select
        customer_month.*,

        customer_month.beginning_arr_gbp > 0 as is_beginning_active_customer,
        customer_month.ending_active_arr_gbp > 0 as is_ending_active_customer,

        customer_month.beginning_arr_gbp > 0
            and customer_month.ending_active_arr_gbp > 0 as is_retained_customer,

        customer_month.beginning_arr_gbp > 0
            and customer_month.ending_active_arr_gbp = 0
            and customer_month.churn_arr_gbp > 0 as is_churned_customer,

        customer_month.beginning_arr_gbp > 0
            and customer_month.ending_active_arr_gbp = 0
            and customer_month.pause_arr_gbp > 0
            and customer_month.churn_arr_gbp = 0 as is_paused_customer,

        customer_month.beginning_arr_gbp > 0
            and customer_month.ending_active_arr_gbp = 0
            and customer_month.churn_arr_gbp = 0
            and customer_month.pause_arr_gbp = 0 as is_inactive_without_churn_or_pause_customer,

        customer_month.beginning_arr_gbp = 0
            and customer_month.ending_active_arr_gbp > 0
            and customer_month.new_business_arr_gbp > 0 as is_new_customer,

        customer_month.new_business_arr_gbp > 0 as has_new_business_arr,
        customer_month.expansion_arr_gbp > 0 as has_expansion_arr,
        customer_month.price_increase_arr_gbp > 0 as has_price_increase_arr,
        customer_month.contraction_arr_gbp > 0 as has_contraction_arr,
        customer_month.churn_arr_gbp > 0 as has_churn_arr,
        customer_month.pause_arr_gbp > 0 as has_pause_arr

    from customer_month

),

final as (

    select
        md5(
            cast(customer_flags.reporting_month_date_hk as varchar)
            || '|'
            || cast(customer_flags.customer_hk as varchar)
            || '|'
            || cast(customer_flags.region_hk as varchar)
            || '|'
            || cast(customer_flags.customer_segment as varchar)
        ) as saas_retention_hk,

        customer_flags.reporting_month_date_hk,
        customer_flags.reporting_month_date,
        customer_flags.customer_hk,
        customer_flags.region_hk,
        customer_flags.customer_segment,

        customer_flags.subscription_count,
        customer_flags.active_subscription_count,
        customer_flags.paused_subscription_count,
        customer_flags.churned_subscription_count,

        customer_flags.beginning_arr_gbp,
        customer_flags.ending_arr_gbp,
        customer_flags.ending_active_arr_gbp,
        customer_flags.paused_arr_balance_gbp,

        customer_flags.beginning_mrr_gbp,
        customer_flags.ending_mrr_gbp,
        customer_flags.ending_active_mrr_gbp,

        customer_flags.new_business_arr_gbp,
        customer_flags.expansion_arr_gbp,
        customer_flags.price_increase_arr_gbp,
        customer_flags.gross_expansion_arr_gbp,
        customer_flags.contraction_arr_gbp,
        customer_flags.churn_arr_gbp,
        customer_flags.pause_arr_gbp,
        customer_flags.renewal_arr_delta_gbp,
        customer_flags.net_arr_delta_gbp,

        greatest(
            customer_flags.beginning_arr_gbp
            - customer_flags.contraction_arr_gbp
            - customer_flags.churn_arr_gbp
            - customer_flags.pause_arr_gbp,
            0
        ) as gross_retained_arr_gbp,

        (
            customer_flags.beginning_arr_gbp
            + customer_flags.expansion_arr_gbp
            + customer_flags.price_increase_arr_gbp
            - customer_flags.contraction_arr_gbp
            - customer_flags.churn_arr_gbp
            - customer_flags.pause_arr_gbp
        ) as net_retained_arr_gbp,

        (
            customer_flags.beginning_arr_gbp
            + customer_flags.expansion_arr_gbp
            + customer_flags.price_increase_arr_gbp
            - customer_flags.contraction_arr_gbp
            - customer_flags.churn_arr_gbp
            - customer_flags.pause_arr_gbp
            + customer_flags.renewal_arr_delta_gbp
        ) as net_retained_arr_including_renewal_gbp,

        case
            when customer_flags.beginning_arr_gbp > 0
                then least(
                    greatest(
                        (
                            customer_flags.beginning_arr_gbp
                            - customer_flags.contraction_arr_gbp
                            - customer_flags.churn_arr_gbp
                            - customer_flags.pause_arr_gbp
                        ) / customer_flags.beginning_arr_gbp,
                        0
                    ),
                    1
                )
            else null
        end as gross_revenue_retention_rate,

        case
            when customer_flags.beginning_arr_gbp > 0
                then (
                    customer_flags.beginning_arr_gbp
                    + customer_flags.expansion_arr_gbp
                    + customer_flags.price_increase_arr_gbp
                    - customer_flags.contraction_arr_gbp
                    - customer_flags.churn_arr_gbp
                    - customer_flags.pause_arr_gbp
                ) / customer_flags.beginning_arr_gbp
            else null
        end as net_revenue_retention_rate,

        case
            when customer_flags.beginning_arr_gbp > 0
                then (
                    customer_flags.beginning_arr_gbp
                    + customer_flags.expansion_arr_gbp
                    + customer_flags.price_increase_arr_gbp
                    - customer_flags.contraction_arr_gbp
                    - customer_flags.churn_arr_gbp
                    - customer_flags.pause_arr_gbp
                    + customer_flags.renewal_arr_delta_gbp
                ) / customer_flags.beginning_arr_gbp
            else null
        end as net_revenue_retention_including_renewal_rate,

        case when customer_flags.beginning_arr_gbp > 0 then customer_flags.gross_expansion_arr_gbp / customer_flags.beginning_arr_gbp else null end as expansion_rate,
        case when customer_flags.beginning_arr_gbp > 0 then customer_flags.price_increase_arr_gbp / customer_flags.beginning_arr_gbp else null end as price_increase_rate,
        case when customer_flags.beginning_arr_gbp > 0 then customer_flags.contraction_arr_gbp / customer_flags.beginning_arr_gbp else null end as contraction_rate,
        case when customer_flags.beginning_arr_gbp > 0 then customer_flags.churn_arr_gbp / customer_flags.beginning_arr_gbp else null end as gross_dollar_churn_rate,
        case when customer_flags.beginning_arr_gbp > 0 then customer_flags.pause_arr_gbp / customer_flags.beginning_arr_gbp else null end as pause_rate,

        cast(customer_flags.is_beginning_active_customer as integer) as beginning_active_customer_count,
        cast(customer_flags.is_ending_active_customer as integer) as ending_active_customer_count,
        cast(customer_flags.is_retained_customer as integer) as retained_customer_count,
        cast(customer_flags.is_churned_customer as integer) as churned_customer_count,
        cast(customer_flags.is_paused_customer as integer) as paused_customer_count,
        cast(customer_flags.is_new_customer as integer) as new_customer_count,
        cast(customer_flags.is_inactive_without_churn_or_pause_customer as integer) as inactive_without_churn_or_pause_customer_count,

        customer_flags.is_beginning_active_customer,
        customer_flags.is_ending_active_customer,
        customer_flags.is_retained_customer,
        customer_flags.is_churned_customer,
        customer_flags.is_paused_customer,
        customer_flags.is_new_customer,
        customer_flags.is_inactive_without_churn_or_pause_customer,

        customer_flags.event_count,
        customer_flags.new_event_count,
        customer_flags.renewal_event_count,
        customer_flags.expansion_event_count,
        customer_flags.price_increase_event_count,
        customer_flags.contraction_event_count,
        customer_flags.churn_event_count,
        customer_flags.pause_event_count,

        customer_flags.has_new_business_arr,
        customer_flags.has_expansion_arr,
        customer_flags.has_price_increase_arr,
        customer_flags.has_contraction_arr,
        customer_flags.has_churn_arr,
        customer_flags.has_pause_arr,
        customer_flags.new_business_arr_gbp > 0 as is_new_business_excluded_from_retention,

        customer_flags.arr_identity_break_event_count,
        customer_flags.mrr_identity_break_event_count,
        customer_flags.arr_continuity_break_count,
        customer_flags.mrr_continuity_break_count,
        customer_flags.negative_arr_balance_subscription_month_count,
        customer_flags.negative_mrr_balance_subscription_month_count,
        customer_flags.missing_subscription_master_subscription_month_count,
        customer_flags.arr_identity_variance_gbp,
        customer_flags.mrr_identity_variance_gbp,

        (
            customer_flags.arr_identity_break_event_count > 0
            or customer_flags.mrr_identity_break_event_count > 0
            or customer_flags.arr_continuity_break_count > 0
            or customer_flags.mrr_continuity_break_count > 0
            or customer_flags.negative_arr_balance_subscription_month_count > 0
            or customer_flags.negative_mrr_balance_subscription_month_count > 0
            or customer_flags.missing_subscription_master_subscription_month_count > 0
            or customer_flags.is_inactive_without_churn_or_pause_customer
        ) as has_saas_retention_control_issue

    from customer_flags

)

select *
from final
