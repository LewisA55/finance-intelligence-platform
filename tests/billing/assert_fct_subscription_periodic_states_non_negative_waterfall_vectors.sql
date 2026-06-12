select *
from {{ ref('fct_subscription_periodic_states') }}
where new_business_arr_gbp < 0
   or expansion_arr_gbp < 0
   or price_increase_arr_gbp < 0
   or gross_expansion_arr_gbp < 0
   or contraction_arr_gbp < 0
   or churn_arr_gbp < 0
   or pause_arr_gbp < 0
   or paused_arr_balance_gbp < 0
   or active_arr_gbp < 0
   or active_mrr_gbp < 0
