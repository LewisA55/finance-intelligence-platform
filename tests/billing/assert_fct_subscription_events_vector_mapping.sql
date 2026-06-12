select *
from {{ ref('fct_subscription_events') }}
where
    new_business_arr_gbp <> case when event_type = 'New' and arr_delta_gbp > 0 then arr_delta_gbp else 0 end
    or expansion_arr_gbp <> case when event_type = 'Expansion' and arr_delta_gbp > 0 then arr_delta_gbp else 0 end
    or price_increase_arr_gbp <> case when event_type = 'Price Increase' and arr_delta_gbp > 0 then arr_delta_gbp else 0 end
    or gross_expansion_arr_gbp <> case when event_type in ('Expansion', 'Price Increase') and arr_delta_gbp > 0 then arr_delta_gbp else 0 end
    or contraction_arr_gbp <> case when event_type = 'Contraction' and arr_delta_gbp < 0 then abs(arr_delta_gbp) else 0 end
    or churn_arr_gbp <> case when event_type = 'Churn' and arr_delta_gbp < 0 then abs(arr_delta_gbp) else 0 end
    or pause_arr_gbp <> case when event_type = 'Pause' and arr_delta_gbp < 0 then abs(arr_delta_gbp) else 0 end
    or renewal_arr_delta_gbp <> case when event_type = 'Renewal' then arr_delta_gbp else 0 end
