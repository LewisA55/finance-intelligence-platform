select *
from {{ ref('mart_executive_cfo_command_center') }}
where (reporting_scope = 'Region Total' and (has_financial_performance_metrics or has_workforce_metrics or has_ap_metrics or has_deferred_revenue_metrics))
   or (reporting_scope = 'Business Unit Total' and (has_o2c_metrics or has_revenue_waterfall_metrics or has_saas_arr_metrics or has_saas_retention_metrics or has_ap_metrics or has_deferred_revenue_metrics))
