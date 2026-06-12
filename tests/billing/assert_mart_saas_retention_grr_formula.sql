select *
from {{ ref('mart_saas_retention') }}
where beginning_arr_gbp > 0
  and round(
        gross_revenue_retention_rate
        - least(
            greatest(
                (beginning_arr_gbp - contraction_arr_gbp - churn_arr_gbp - pause_arr_gbp)
                / beginning_arr_gbp,
                0
            ),
            1
        ),
        6
      ) <> 0
