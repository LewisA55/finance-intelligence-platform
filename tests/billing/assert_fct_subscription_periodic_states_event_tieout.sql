with state_movements as (

    select
        subscription_id,
        reporting_month_date as event_month_date,
        event_count,
        new_business_arr_gbp,
        expansion_arr_gbp,
        price_increase_arr_gbp,
        gross_expansion_arr_gbp,
        contraction_arr_gbp,
        churn_arr_gbp,
        pause_arr_gbp,
        renewal_arr_delta_gbp,
        net_arr_delta_gbp,
        net_mrr_delta_gbp
    from {{ ref('fct_subscription_periodic_states') }}
    where event_count > 0

),

event_movements as (

    select
        subscription_id,
        event_month_date,
        count(*) as event_count,
        sum(new_business_arr_gbp) as new_business_arr_gbp,
        sum(expansion_arr_gbp) as expansion_arr_gbp,
        sum(price_increase_arr_gbp) as price_increase_arr_gbp,
        sum(gross_expansion_arr_gbp) as gross_expansion_arr_gbp,
        sum(contraction_arr_gbp) as contraction_arr_gbp,
        sum(churn_arr_gbp) as churn_arr_gbp,
        sum(pause_arr_gbp) as pause_arr_gbp,
        sum(renewal_arr_delta_gbp) as renewal_arr_delta_gbp,
        sum(net_arr_delta_gbp) as net_arr_delta_gbp,
        sum(net_mrr_delta_gbp) as net_mrr_delta_gbp
    from {{ ref('fct_subscription_events') }}
    group by 1, 2

)

select
    coalesce(state_movements.subscription_id, event_movements.subscription_id) as subscription_id,
    coalesce(state_movements.event_month_date, event_movements.event_month_date) as event_month_date
from state_movements
full outer join event_movements
    on state_movements.subscription_id = event_movements.subscription_id
   and state_movements.event_month_date = event_movements.event_month_date
where coalesce(state_movements.event_count, 0) <> coalesce(event_movements.event_count, 0)
   or round(coalesce(state_movements.new_business_arr_gbp, 0) - coalesce(event_movements.new_business_arr_gbp, 0), 2) <> 0
   or round(coalesce(state_movements.expansion_arr_gbp, 0) - coalesce(event_movements.expansion_arr_gbp, 0), 2) <> 0
   or round(coalesce(state_movements.price_increase_arr_gbp, 0) - coalesce(event_movements.price_increase_arr_gbp, 0), 2) <> 0
   or round(coalesce(state_movements.gross_expansion_arr_gbp, 0) - coalesce(event_movements.gross_expansion_arr_gbp, 0), 2) <> 0
   or round(coalesce(state_movements.contraction_arr_gbp, 0) - coalesce(event_movements.contraction_arr_gbp, 0), 2) <> 0
   or round(coalesce(state_movements.churn_arr_gbp, 0) - coalesce(event_movements.churn_arr_gbp, 0), 2) <> 0
   or round(coalesce(state_movements.pause_arr_gbp, 0) - coalesce(event_movements.pause_arr_gbp, 0), 2) <> 0
   or round(coalesce(state_movements.renewal_arr_delta_gbp, 0) - coalesce(event_movements.renewal_arr_delta_gbp, 0), 2) <> 0
   or round(coalesce(state_movements.net_arr_delta_gbp, 0) - coalesce(event_movements.net_arr_delta_gbp, 0), 2) <> 0
   or round(coalesce(state_movements.net_mrr_delta_gbp, 0) - coalesce(event_movements.net_mrr_delta_gbp, 0), 2) <> 0
