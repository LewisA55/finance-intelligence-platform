with lagged as (

    select
        subscription_id,
        reporting_month_date,
        beginning_arr_gbp,
        lag(ending_arr_gbp) over (
            partition by subscription_id
            order by reporting_month_date
        ) as prior_ending_arr_gbp,
        beginning_mrr_gbp,
        lag(ending_mrr_gbp) over (
            partition by subscription_id
            order by reporting_month_date
        ) as prior_ending_mrr_gbp
    from {{ ref('fct_subscription_periodic_states') }}

)

select *
from lagged
where prior_ending_arr_gbp is not null
  and (
        round(beginning_arr_gbp - prior_ending_arr_gbp, 2) <> 0
     or round(beginning_mrr_gbp - prior_ending_mrr_gbp, 2) <> 0
  )
