/*
Purpose:
    Ensure actual-versus-forecast GBP variance arithmetic is correct for actual periods.

Expected result:
    Zero rows.
*/

select
    variance_extract_pk,
    variance_extract_line_id,
    period_status,
    actual_amount_gbp,
    forecast_amount_gbp,
    actual_vs_forecast_variance_gbp,
    actual_amount_gbp - forecast_amount_gbp as expected_variance_gbp
from {{ ref('stg_planning__variance_source_extract') }}
where period_status = 'Actual'
  and abs(actual_vs_forecast_variance_gbp - (actual_amount_gbp - forecast_amount_gbp)) > 0.01
