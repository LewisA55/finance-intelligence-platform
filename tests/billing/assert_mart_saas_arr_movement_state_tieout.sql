with mart_totals as (

    select
        sum(beginning_arr_gbp) as beginning_arr_gbp,
        sum(new_business_arr_gbp) as new_business_arr_gbp,
        sum(expansion_arr_gbp) as expansion_arr_gbp,
        sum(price_increase_arr_gbp) as price_increase_arr_gbp,
        sum(contraction_arr_gbp) as contraction_arr_gbp,
        sum(churn_arr_gbp) as churn_arr_gbp,
        sum(pause_arr_gbp) as pause_arr_gbp,
        sum(renewal_arr_delta_gbp) as renewal_arr_delta_gbp,
        sum(net_arr_delta_gbp) as net_arr_delta_gbp,
        sum(ending_arr_gbp) as ending_arr_gbp,
        sum(active_arr_gbp) as active_arr_gbp
    from {{ ref('mart_saas_arr_movement') }}

),

state_totals as (

    select
        sum(beginning_arr_gbp) as beginning_arr_gbp,
        sum(new_business_arr_gbp) as new_business_arr_gbp,
        sum(expansion_arr_gbp) as expansion_arr_gbp,
        sum(price_increase_arr_gbp) as price_increase_arr_gbp,
        sum(contraction_arr_gbp) as contraction_arr_gbp,
        sum(churn_arr_gbp) as churn_arr_gbp,
        sum(pause_arr_gbp) as pause_arr_gbp,
        sum(renewal_arr_delta_gbp) as renewal_arr_delta_gbp,
        sum(net_arr_delta_gbp) as net_arr_delta_gbp,
        sum(ending_arr_gbp) as ending_arr_gbp,
        sum(active_arr_gbp) as active_arr_gbp
    from {{ ref('fct_subscription_periodic_states') }}

)

select *
from mart_totals
cross join state_totals
where round(mart_totals.beginning_arr_gbp - state_totals.beginning_arr_gbp, 2) <> 0
   or round(mart_totals.new_business_arr_gbp - state_totals.new_business_arr_gbp, 2) <> 0
   or round(mart_totals.expansion_arr_gbp - state_totals.expansion_arr_gbp, 2) <> 0
   or round(mart_totals.price_increase_arr_gbp - state_totals.price_increase_arr_gbp, 2) <> 0
   or round(mart_totals.contraction_arr_gbp - state_totals.contraction_arr_gbp, 2) <> 0
   or round(mart_totals.churn_arr_gbp - state_totals.churn_arr_gbp, 2) <> 0
   or round(mart_totals.pause_arr_gbp - state_totals.pause_arr_gbp, 2) <> 0
   or round(mart_totals.renewal_arr_delta_gbp - state_totals.renewal_arr_delta_gbp, 2) <> 0
   or round(mart_totals.net_arr_delta_gbp - state_totals.net_arr_delta_gbp, 2) <> 0
   or round(mart_totals.ending_arr_gbp - state_totals.ending_arr_gbp, 2) <> 0
   or round(mart_totals.active_arr_gbp - state_totals.active_arr_gbp, 2) <> 0
