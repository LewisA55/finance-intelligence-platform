/*
Purpose:
    Ensure forecast-versus-budget GBP variance arithmetic is correct for all variance source lines.

Expected result:
    Zero rows.
*/

select
    variance_extract_pk,
    variance_extract_line_id,
    period_status,
    forecast_amount_gbp,
    budget_amount_gbp,
    forecast_vs_budget_variance_gbp,
    forecast_amount_gbp - budget_amount_gbp as expected_variance_gbp
from {{ ref('stg_planning__variance_source_extract') }}
where abs(forecast_vs_budget_variance_gbp - (forecast_amount_gbp - budget_amount_gbp)) > 0.01
