select *
from {{ ref('mart_saas_arr_movement') }}
where arr_waterfall_variance_gbp <> 0
   or round(calculated_net_arr_movement_gbp - net_arr_delta_gbp, 2) <> 0
