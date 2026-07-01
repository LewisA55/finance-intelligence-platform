select *
from {{ ref('mart_model_actuals_feed') }}
where use_in_excel_actuals_flag <> (
    is_actual_period
    and has_revenue_actuals
    and has_o2c_actuals
    and has_financial_actuals
    and model_blocking_exception_count = 0
)
   or (is_actual_period and is_scheduled_period)
