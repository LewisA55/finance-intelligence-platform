select *
from {{ ref('mart_saas_retention') }}
where gross_revenue_retention_rate < 0
   or gross_revenue_retention_rate > 1
   or expansion_rate < 0
   or price_increase_rate < 0
   or contraction_rate < 0
   or gross_dollar_churn_rate < 0
   or pause_rate < 0
