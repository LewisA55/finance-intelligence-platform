select *
from {{ ref('mart_saas_arr_movement') }}
where gross_expansion_rate < 0
   or contraction_rate < 0
   or churn_rate < 0
   or pause_rate < 0
   or active_arr_ratio < 0
   or active_arr_ratio > 1
