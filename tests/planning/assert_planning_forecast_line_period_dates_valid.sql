/*
Purpose:
    Ensure forecast line period dates are chronologically valid and posting period equals the month start derived from period_start_date.

Expected result:
    Zero rows.
*/

select
    forecast_line_pk,
    forecast_line_id,
    forecast_version_code,
    scenario_type,
    posting_period,
    period_start_date,
    period_end_date,
    cast(date_trunc('month', period_start_date) as date) as expected_posting_period
from {{ ref('stg_planning__forecast_lines') }}
where period_start_date > period_end_date
   or posting_period != cast(date_trunc('month', period_start_date) as date)
