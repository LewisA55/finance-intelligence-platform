/*
    Test: mart_deferred_revenue_control rollforward exception flags agree to variance amounts.

    Failure condition:
    A row has rollforward variance but is not flagged, or is flagged with no
    rollforward variance.
*/

select
    deferred_revenue_control_hk,
    period_month,
    period_status,
    currency_code,
    revenue_category,
    corporate_rollforward_variance_gbp,
    corporate_rollforward_exception_count,
    has_rollforward_arithmetic_exception
from {{ ref('mart_deferred_revenue_control') }}
where (
        abs(corporate_rollforward_variance_gbp) > 0.01
        and has_rollforward_arithmetic_exception = false
      )
   or (
        abs(corporate_rollforward_variance_gbp) <= 0.01
        and has_rollforward_arithmetic_exception = true
      )
