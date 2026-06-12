{{ config(
    materialized = 'table',
    schema = 'gold'
) }}

with states as (

    select *
    from {{ ref('fct_subscription_periodic_states') }}

),

aggregated as (

    select
        states.reporting_month_date_hk,
        states.reporting_month_date,
        states.customer_hk,
        states.region_hk,
        coalesce(cast(states.product_id as varchar), 'UNKNOWN_PRODUCT') as product_id,
        coalesce(states.customer_segment, 'Unknown') as customer_segment,

        count(distinct states.subscription_id) as subscription_count,
        sum(case when states.is_active_subscription_month then 1 else 0 end) as active_subscription_count,
        sum(case when states.is_paused_subscription_month then 1 else 0 end) as paused_subscription_count,
        sum(case when states.is_churned_subscription_month then 1 else 0 end) as churned_subscription_count,

        sum(case when states.new_event_count > 0 then 1 else 0 end) as new_subscription_event_count,
        sum(case when states.expansion_event_count > 0 then 1 else 0 end) as expanded_subscription_event_count,
        sum(case when states.price_increase_event_count > 0 then 1 else 0 end) as price_increase_subscription_event_count,
        sum(case when states.contraction_event_count > 0 then 1 else 0 end) as contracted_subscription_event_count,
        sum(case when states.churn_event_count > 0 then 1 else 0 end) as churned_subscription_event_count,
        sum(case when states.pause_event_count > 0 then 1 else 0 end) as paused_subscription_event_count,
        sum(case when states.renewal_event_count > 0 then 1 else 0 end) as renewed_subscription_event_count,

        sum(states.event_count) as event_count,

        sum(states.beginning_arr_gbp) as beginning_arr_gbp,
        sum(states.new_business_arr_gbp) as new_business_arr_gbp,
        sum(states.expansion_arr_gbp) as expansion_arr_gbp,
        sum(states.price_increase_arr_gbp) as price_increase_arr_gbp,
        sum(states.gross_expansion_arr_gbp) as gross_expansion_arr_gbp,
        sum(states.contraction_arr_gbp) as contraction_arr_gbp,
        sum(states.churn_arr_gbp) as churn_arr_gbp,
        sum(states.pause_arr_gbp) as pause_arr_gbp,
        sum(states.renewal_arr_delta_gbp) as renewal_arr_delta_gbp,
        sum(states.net_arr_delta_gbp) as net_arr_delta_gbp,
        sum(states.ending_arr_gbp) as ending_arr_gbp,
        sum(states.active_arr_gbp) as active_arr_gbp,
        sum(states.paused_arr_balance_gbp) as paused_arr_balance_gbp,

        sum(states.beginning_mrr_gbp) as beginning_mrr_gbp,
        sum(states.net_mrr_delta_gbp) as net_mrr_delta_gbp,
        sum(states.ending_mrr_gbp) as ending_mrr_gbp,
        sum(states.active_mrr_gbp) as active_mrr_gbp,

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
    group by 1, 2, 3, 4, 5, 6

),

final as (

    select
        md5(
            cast(aggregated.reporting_month_date_hk as varchar)
            || '|'
            || cast(aggregated.customer_hk as varchar)
            || '|'
            || cast(aggregated.region_hk as varchar)
            || '|'
            || cast(aggregated.product_id as varchar)
            || '|'
            || cast(aggregated.customer_segment as varchar)
        ) as saas_arr_movement_hk,

        aggregated.reporting_month_date_hk,
        aggregated.reporting_month_date,
        aggregated.customer_hk,
        aggregated.region_hk,
        aggregated.product_id,
        aggregated.customer_segment,

        aggregated.subscription_count,
        aggregated.active_subscription_count,
        aggregated.paused_subscription_count,
        aggregated.churned_subscription_count,
        aggregated.new_subscription_event_count,
        aggregated.expanded_subscription_event_count,
        aggregated.price_increase_subscription_event_count,
        aggregated.contracted_subscription_event_count,
        aggregated.churned_subscription_event_count,
        aggregated.paused_subscription_event_count,
        aggregated.renewed_subscription_event_count,
        aggregated.event_count,

        aggregated.beginning_arr_gbp,
        aggregated.new_business_arr_gbp,
        aggregated.expansion_arr_gbp,
        aggregated.price_increase_arr_gbp,
        aggregated.gross_expansion_arr_gbp,
        aggregated.contraction_arr_gbp,
        aggregated.churn_arr_gbp,
        aggregated.pause_arr_gbp,
        aggregated.renewal_arr_delta_gbp,

        (
            aggregated.new_business_arr_gbp
            + aggregated.expansion_arr_gbp
            + aggregated.price_increase_arr_gbp
            - aggregated.contraction_arr_gbp
            - aggregated.churn_arr_gbp
            - aggregated.pause_arr_gbp
            + aggregated.renewal_arr_delta_gbp
        ) as calculated_net_arr_movement_gbp,

        aggregated.net_arr_delta_gbp,
        aggregated.ending_arr_gbp,
        aggregated.active_arr_gbp,
        aggregated.paused_arr_balance_gbp,

        aggregated.beginning_mrr_gbp,
        aggregated.net_mrr_delta_gbp,
        aggregated.ending_mrr_gbp,
        aggregated.active_mrr_gbp,

        case
            when aggregated.beginning_arr_gbp > 0
                then aggregated.gross_expansion_arr_gbp / aggregated.beginning_arr_gbp
            else 0
        end as gross_expansion_rate,

        case
            when aggregated.beginning_arr_gbp > 0
                then aggregated.contraction_arr_gbp / aggregated.beginning_arr_gbp
            else 0
        end as contraction_rate,

        case
            when aggregated.beginning_arr_gbp > 0
                then aggregated.churn_arr_gbp / aggregated.beginning_arr_gbp
            else 0
        end as churn_rate,

        case
            when aggregated.beginning_arr_gbp > 0
                then aggregated.pause_arr_gbp / aggregated.beginning_arr_gbp
            else 0
        end as pause_rate,

        case
            when aggregated.beginning_arr_gbp > 0
                then (
                    aggregated.new_business_arr_gbp
                    + aggregated.expansion_arr_gbp
                    + aggregated.price_increase_arr_gbp
                    - aggregated.contraction_arr_gbp
                    - aggregated.churn_arr_gbp
                    - aggregated.pause_arr_gbp
                    + aggregated.renewal_arr_delta_gbp
                ) / aggregated.beginning_arr_gbp
            else 0
        end as net_arr_movement_rate,

        case
            when aggregated.ending_arr_gbp > 0
                then aggregated.active_arr_gbp / aggregated.ending_arr_gbp
            else 0
        end as active_arr_ratio,

        aggregated.arr_identity_break_event_count,
        aggregated.mrr_identity_break_event_count,
        aggregated.arr_continuity_break_count,
        aggregated.mrr_continuity_break_count,
        aggregated.negative_arr_balance_subscription_month_count,
        aggregated.negative_mrr_balance_subscription_month_count,
        aggregated.missing_subscription_master_subscription_month_count,
        aggregated.arr_identity_variance_gbp,
        aggregated.mrr_identity_variance_gbp,

        aggregated.new_business_arr_gbp > 0 as has_new_business_arr,
        aggregated.expansion_arr_gbp > 0 as has_expansion_arr,
        aggregated.price_increase_arr_gbp > 0 as has_price_increase_arr,
        aggregated.contraction_arr_gbp > 0 as has_contraction_arr,
        aggregated.churn_arr_gbp > 0 as has_churn_arr,
        aggregated.pause_arr_gbp > 0 as has_pause_arr,
        aggregated.renewal_arr_delta_gbp <> 0 as has_renewal_arr_delta,

        (
            aggregated.arr_identity_break_event_count > 0
            or aggregated.mrr_identity_break_event_count > 0
            or aggregated.arr_continuity_break_count > 0
            or aggregated.mrr_continuity_break_count > 0
            or aggregated.negative_arr_balance_subscription_month_count > 0
            or aggregated.negative_mrr_balance_subscription_month_count > 0
            or aggregated.missing_subscription_master_subscription_month_count > 0
        ) as has_saas_control_issue,

        round(
            aggregated.ending_arr_gbp
            - aggregated.beginning_arr_gbp
            - aggregated.new_business_arr_gbp
            - aggregated.expansion_arr_gbp
            - aggregated.price_increase_arr_gbp
            + aggregated.contraction_arr_gbp
            + aggregated.churn_arr_gbp
            + aggregated.pause_arr_gbp
            - aggregated.renewal_arr_delta_gbp,
            2
        ) as arr_waterfall_variance_gbp

    from aggregated

)

select *
from final
