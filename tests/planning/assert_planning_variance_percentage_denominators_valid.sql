/*
Purpose:
    Ensure variance percentage nullability follows denominator logic.

Expected result:
    Zero rows.
*/

select
    variance_extract_pk,
    variance_extract_line_id,
    period_status,
    actual_amount_gbp,
    budget_amount_gbp,
    forecast_amount_gbp,
    actual_vs_budget_variance_pct,
    actual_vs_forecast_variance_pct,
    forecast_vs_budget_variance_pct
from {{ ref('stg_planning__variance_source_extract') }}
where
    (
        period_status = 'Actual'
        and budget_amount_gbp != 0
        and actual_vs_budget_variance_pct is null
    )
    or
    (
        period_status = 'Actual'
        and forecast_amount_gbp != 0
        and actual_vs_forecast_variance_pct is null
    )
    or
    (
        budget_amount_gbp != 0
        and forecast_vs_budget_variance_pct is null
    )
