/*
    Test: mart_financial_performance variance arithmetic.

    Failure condition:
    Any row where a populated variance amount does not match the difference
    between its underlying measures within a 0.01 GBP tolerance.
*/

select
    variance_extract_line_id,
    actual_amount_gbp,
    budget_amount_gbp,
    forecast_amount_gbp,
    actual_vs_budget_variance_gbp,
    actual_vs_forecast_variance_gbp,
    forecast_vs_budget_variance_gbp
from {{ ref('mart_financial_performance') }}
where
    (
        actual_vs_budget_variance_gbp is not null
        and abs(round(actual_amount_gbp - budget_amount_gbp, 2) - round(actual_vs_budget_variance_gbp, 2)) > 0.01
    )
    or
    (
        actual_vs_forecast_variance_gbp is not null
        and abs(round(actual_amount_gbp - forecast_amount_gbp, 2) - round(actual_vs_forecast_variance_gbp, 2)) > 0.01
    )
    or
    (
        forecast_vs_budget_variance_gbp is not null
        and abs(round(forecast_amount_gbp - budget_amount_gbp, 2) - round(forecast_vs_budget_variance_gbp, 2)) > 0.01
    )
