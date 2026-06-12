{{ config(
    materialized = 'table',
    schema = 'gold'
) }}

with events as (

    select *
    from {{ ref('fct_subscription_events') }}

),

dim_date as (

    select
        date_hk,
        date_day
    from {{ ref('dim_date') }}
    where date_day is not null

),

subscription_scope as (

    select *
    from (

        select
            events.subscription_id,
            events.customer_id,
            events.customer_hk,
            events.region_hk,
            events.product_id,
            events.customer_segment,
            events.plan_tier,
            events.contract_status,
            events.billing_frequency,
            events.contract_start_date,
            events.contract_end_date,
            events.has_missing_subscription_master,
            events.is_subscription_defect,
            events.subscription_defect_type,
            row_number() over (
                partition by events.subscription_id
                order by events.event_date desc, events.event_sequence desc
            ) as rn
        from events

    )
    where rn = 1

),

subscription_first_month as (

    select
        subscription_id,
        min(event_month_date) as first_event_month_date
    from events
    group by 1

),

event_month_bounds as (

    select
        min(event_month_date) as min_event_month_date,
        max(event_month_date) as max_event_month_date
    from events

),

month_spine as (

    select
        dim_date.date_day as reporting_month_date,
        dim_date.date_hk as reporting_month_date_hk
    from dim_date
    cross join event_month_bounds
    where dim_date.date_day = cast(date_trunc('month', dim_date.date_day) as date)
      and dim_date.date_day between event_month_bounds.min_event_month_date
                              and event_month_bounds.max_event_month_date

),

subscription_month_spine as (

    select
        subscription_scope.subscription_id,
        subscription_scope.customer_id,
        subscription_scope.customer_hk,
        subscription_scope.region_hk,
        subscription_scope.product_id,
        subscription_scope.customer_segment,
        subscription_scope.plan_tier,
        subscription_scope.contract_status,
        subscription_scope.billing_frequency,
        subscription_scope.contract_start_date,
        subscription_scope.contract_end_date,
        subscription_scope.has_missing_subscription_master,
        subscription_scope.is_subscription_defect,
        subscription_scope.subscription_defect_type,
        month_spine.reporting_month_date,
        month_spine.reporting_month_date_hk
    from subscription_scope

    inner join subscription_first_month
        on subscription_scope.subscription_id = subscription_first_month.subscription_id

    inner join month_spine
        on month_spine.reporting_month_date >= subscription_first_month.first_event_month_date

),

monthly_events as (

    select
        subscription_id,
        event_month_date as reporting_month_date,

        count(*) as event_count,

        sum(case when is_new_event then 1 else 0 end) as new_event_count,
        sum(case when is_renewal_event then 1 else 0 end) as renewal_event_count,
        sum(case when is_expansion_event then 1 else 0 end) as expansion_event_count,
        sum(case when is_price_increase_event then 1 else 0 end) as price_increase_event_count,
        sum(case when is_contraction_event then 1 else 0 end) as contraction_event_count,
        sum(case when is_churn_event then 1 else 0 end) as churn_event_count,
        sum(case when is_pause_event then 1 else 0 end) as pause_event_count,
        sum(case when is_terminal_event then 1 else 0 end) as terminal_event_count,

        sum(new_business_arr_gbp) as new_business_arr_gbp,
        sum(expansion_arr_gbp) as expansion_arr_gbp,
        sum(price_increase_arr_gbp) as price_increase_arr_gbp,
        sum(gross_expansion_arr_gbp) as gross_expansion_arr_gbp,
        sum(contraction_arr_gbp) as contraction_arr_gbp,
        sum(churn_arr_gbp) as churn_arr_gbp,
        sum(pause_arr_gbp) as pause_arr_gbp,
        sum(renewal_arr_delta_gbp) as renewal_arr_delta_gbp,
        sum(net_arr_delta_gbp) as net_arr_delta_gbp,

        sum(net_mrr_delta_gbp) as net_mrr_delta_gbp,

        sum(case when has_arr_identity_break then 1 else 0 end) as arr_identity_break_event_count,
        sum(case when has_mrr_identity_break then 1 else 0 end) as mrr_identity_break_event_count,
        sum(case when has_missing_subscription_master then 1 else 0 end) as missing_subscription_master_event_count,

        sum(arr_identity_variance_gbp) as arr_identity_variance_gbp,
        sum(mrr_identity_variance_gbp) as mrr_identity_variance_gbp

    from events
    group by 1, 2

),

joined as (

    select
        subscription_month_spine.subscription_id,
        subscription_month_spine.customer_id,
        subscription_month_spine.customer_hk,
        subscription_month_spine.region_hk,
        subscription_month_spine.product_id,
        subscription_month_spine.customer_segment,
        subscription_month_spine.plan_tier,
        subscription_month_spine.contract_status,
        subscription_month_spine.billing_frequency,
        subscription_month_spine.contract_start_date,
        subscription_month_spine.contract_end_date,
        subscription_month_spine.has_missing_subscription_master,
        subscription_month_spine.is_subscription_defect,
        subscription_month_spine.subscription_defect_type,
        subscription_month_spine.reporting_month_date,
        subscription_month_spine.reporting_month_date_hk,

        coalesce(monthly_events.event_count, 0) as event_count,

        coalesce(monthly_events.new_event_count, 0) as new_event_count,
        coalesce(monthly_events.renewal_event_count, 0) as renewal_event_count,
        coalesce(monthly_events.expansion_event_count, 0) as expansion_event_count,
        coalesce(monthly_events.price_increase_event_count, 0) as price_increase_event_count,
        coalesce(monthly_events.contraction_event_count, 0) as contraction_event_count,
        coalesce(monthly_events.churn_event_count, 0) as churn_event_count,
        coalesce(monthly_events.pause_event_count, 0) as pause_event_count,
        coalesce(monthly_events.terminal_event_count, 0) as terminal_event_count,

        coalesce(monthly_events.new_business_arr_gbp, 0) as new_business_arr_gbp,
        coalesce(monthly_events.expansion_arr_gbp, 0) as expansion_arr_gbp,
        coalesce(monthly_events.price_increase_arr_gbp, 0) as price_increase_arr_gbp,
        coalesce(monthly_events.gross_expansion_arr_gbp, 0) as gross_expansion_arr_gbp,
        coalesce(monthly_events.contraction_arr_gbp, 0) as contraction_arr_gbp,
        coalesce(monthly_events.churn_arr_gbp, 0) as churn_arr_gbp,
        coalesce(monthly_events.pause_arr_gbp, 0) as pause_arr_gbp,
        coalesce(monthly_events.renewal_arr_delta_gbp, 0) as renewal_arr_delta_gbp,
        coalesce(monthly_events.net_arr_delta_gbp, 0) as net_arr_delta_gbp,

        coalesce(monthly_events.net_mrr_delta_gbp, 0) as net_mrr_delta_gbp,

        coalesce(monthly_events.arr_identity_break_event_count, 0) as arr_identity_break_event_count,
        coalesce(monthly_events.mrr_identity_break_event_count, 0) as mrr_identity_break_event_count,
        coalesce(monthly_events.missing_subscription_master_event_count, 0) as missing_subscription_master_event_count,

        coalesce(monthly_events.arr_identity_variance_gbp, 0) as arr_identity_variance_gbp,
        coalesce(monthly_events.mrr_identity_variance_gbp, 0) as mrr_identity_variance_gbp

    from subscription_month_spine

    left join monthly_events
        on subscription_month_spine.subscription_id = monthly_events.subscription_id
       and subscription_month_spine.reporting_month_date = monthly_events.reporting_month_date

),

state_calcs as (

    select
        joined.*,

        coalesce(
            sum(joined.net_arr_delta_gbp) over (
                partition by joined.subscription_id
                order by joined.reporting_month_date
                rows between unbounded preceding and 1 preceding
            ),
            0
        ) as beginning_arr_gbp,

        sum(joined.net_arr_delta_gbp) over (
            partition by joined.subscription_id
            order by joined.reporting_month_date
            rows between unbounded preceding and current row
        ) as ending_arr_gbp,

        coalesce(
            sum(joined.net_mrr_delta_gbp) over (
                partition by joined.subscription_id
                order by joined.reporting_month_date
                rows between unbounded preceding and 1 preceding
            ),
            0
        ) as beginning_mrr_gbp,

        sum(joined.net_mrr_delta_gbp) over (
            partition by joined.subscription_id
            order by joined.reporting_month_date
            rows between unbounded preceding and current row
        ) as ending_mrr_gbp,

        sum(joined.churn_event_count) over (
            partition by joined.subscription_id
            order by joined.reporting_month_date
            rows between unbounded preceding and current row
        ) as cumulative_churn_event_count,

        sum(joined.pause_event_count) over (
            partition by joined.subscription_id
            order by joined.reporting_month_date
            rows between unbounded preceding and current row
        ) as cumulative_pause_event_count,

        sum(joined.pause_arr_gbp) over (
            partition by joined.subscription_id
            order by joined.reporting_month_date
            rows between unbounded preceding and current row
        ) as cumulative_pause_arr_gbp

    from joined

),

final as (

    select
        md5(cast(state_calcs.subscription_id as varchar) || '|' || cast(state_calcs.reporting_month_date as varchar)) as subscription_periodic_state_hk,

        state_calcs.subscription_id,
        state_calcs.customer_id,
        state_calcs.customer_hk,
        state_calcs.region_hk,
        state_calcs.reporting_month_date_hk,
        state_calcs.reporting_month_date,

        state_calcs.product_id,
        state_calcs.customer_segment,
        state_calcs.plan_tier,
        state_calcs.contract_status,
        state_calcs.billing_frequency,
        state_calcs.contract_start_date,
        state_calcs.contract_end_date,

        state_calcs.beginning_arr_gbp,
        state_calcs.new_business_arr_gbp,
        state_calcs.expansion_arr_gbp,
        state_calcs.price_increase_arr_gbp,
        state_calcs.gross_expansion_arr_gbp,
        state_calcs.contraction_arr_gbp,
        state_calcs.churn_arr_gbp,
        state_calcs.pause_arr_gbp,
        state_calcs.renewal_arr_delta_gbp,
        state_calcs.net_arr_delta_gbp,
        state_calcs.ending_arr_gbp,

        state_calcs.beginning_mrr_gbp,
        state_calcs.net_mrr_delta_gbp,
        state_calcs.ending_mrr_gbp,

        state_calcs.cumulative_pause_arr_gbp as paused_arr_balance_gbp,

        state_calcs.event_count,
        state_calcs.new_event_count,
        state_calcs.renewal_event_count,
        state_calcs.expansion_event_count,
        state_calcs.price_increase_event_count,
        state_calcs.contraction_event_count,
        state_calcs.churn_event_count,
        state_calcs.pause_event_count,
        state_calcs.terminal_event_count,

        state_calcs.cumulative_churn_event_count,
        state_calcs.cumulative_pause_event_count,

        state_calcs.cumulative_churn_event_count > 0 as is_churned_subscription_month,
        state_calcs.cumulative_pause_event_count > 0 as is_paused_subscription_month,
        state_calcs.cumulative_churn_event_count = 0
            and state_calcs.cumulative_pause_event_count = 0
            and round(state_calcs.ending_arr_gbp, 2) > 0 as is_active_subscription_month,

        case
            when state_calcs.cumulative_churn_event_count = 0
            and state_calcs.cumulative_pause_event_count = 0
            and round(state_calcs.ending_arr_gbp, 2) > 0
                then state_calcs.ending_arr_gbp
            else 0
        end as active_arr_gbp,

        case
            when state_calcs.cumulative_churn_event_count = 0
            and state_calcs.cumulative_pause_event_count = 0
            and round(state_calcs.ending_mrr_gbp, 2) > 0
                then state_calcs.ending_mrr_gbp
            else 0
        end as active_mrr_gbp,

        round(state_calcs.ending_arr_gbp, 2) < 0 as has_negative_arr_balance,
        round(state_calcs.ending_mrr_gbp, 2) < 0 as has_negative_mrr_balance,

        state_calcs.event_count > 0 as has_subscription_event,
        state_calcs.net_arr_delta_gbp <> 0 as has_arr_movement,
        state_calcs.terminal_event_count > 0 as has_terminal_event,

        state_calcs.arr_identity_break_event_count,
        state_calcs.mrr_identity_break_event_count,
        state_calcs.missing_subscription_master_event_count,
        state_calcs.arr_identity_variance_gbp,
        state_calcs.mrr_identity_variance_gbp,

        state_calcs.arr_identity_break_event_count > 0 as has_arr_identity_break,
        state_calcs.mrr_identity_break_event_count > 0 as has_mrr_identity_break,
        state_calcs.has_missing_subscription_master,
        state_calcs.missing_subscription_master_event_count > 0 as has_missing_subscription_master_event,

        round(
            state_calcs.ending_arr_gbp
            - state_calcs.beginning_arr_gbp
            - state_calcs.net_arr_delta_gbp,
            2
        ) as arr_continuity_variance_gbp,

        round(
            state_calcs.ending_mrr_gbp
            - state_calcs.beginning_mrr_gbp
            - state_calcs.net_mrr_delta_gbp,
            2
        ) as mrr_continuity_variance_gbp,

        round(
            state_calcs.ending_arr_gbp
            - state_calcs.beginning_arr_gbp
            - state_calcs.net_arr_delta_gbp,
            2
        ) <> 0 as has_arr_continuity_break,

        round(
            state_calcs.ending_mrr_gbp
            - state_calcs.beginning_mrr_gbp
            - state_calcs.net_mrr_delta_gbp,
            2
        ) <> 0 as has_mrr_continuity_break,

        state_calcs.is_subscription_defect,
        state_calcs.subscription_defect_type

    from state_calcs

)

select *
from final
