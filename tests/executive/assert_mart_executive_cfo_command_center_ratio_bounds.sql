select *
from {{ ref('mart_executive_cfo_command_center') }}
where cash_collection_rate < 0
   or gross_revenue_retention_rate < 0
   or gross_revenue_retention_rate > 1
   or logo_retention_rate < 0
   or logo_retention_rate > 1
   or logo_churn_rate < 0
   or logo_churn_rate > 1
