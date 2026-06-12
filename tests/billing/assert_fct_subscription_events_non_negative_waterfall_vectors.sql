select *
from {{ ref('fct_subscription_events') }}
where new_business_arr_gbp < 0
   or expansion_arr_gbp < 0
   or price_increase_arr_gbp < 0
   or gross_expansion_arr_gbp < 0
   or contraction_arr_gbp < 0
   or churn_arr_gbp < 0
   or pause_arr_gbp < 0