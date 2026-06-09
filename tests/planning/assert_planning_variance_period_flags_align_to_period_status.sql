/*
Purpose:
    Ensure variance source period flags align to period_status:
      - Actual rows must be actual periods and not forecast periods.
      - Forecast rows must be forecast periods and not actual periods.

Expected result:
    Zero rows.
*/

select
    variance_extract_pk,
    variance_extract_line_id,
    period_status,
    is_actual_period,
    is_forecast_period
from {{ ref('stg_planning__variance_source_extract') }}
where
    (
        period_status = 'Actual'
        and (
            is_actual_period != true
            or is_forecast_period != false
        )
    )
    or
    (
        period_status = 'Forecast'
        and (
            is_actual_period != false
            or is_forecast_period != true
        )
    )
