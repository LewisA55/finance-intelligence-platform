select *
from {{ ref('mart_saas_retention') }}
where beginning_arr_gbp > 0
  and round(
        net_retained_arr_gbp
        - beginning_arr_gbp
        - expansion_arr_gbp
        - price_increase_arr_gbp
        + contraction_arr_gbp
        + churn_arr_gbp
        + pause_arr_gbp,
        2
      ) <> 0
