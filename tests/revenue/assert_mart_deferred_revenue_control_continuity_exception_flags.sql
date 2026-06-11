/*
    Test: mart_deferred_revenue_control continuity exception flags agree to continuity variance.

    Failure condition:
    A row has continuity variance but is not flagged, or is flagged with no
    continuity variance.
*/

select
    deferred_revenue_control_hk,
    period_month,
    period_status,
    currency_code,
    revenue_category,
    corporate_continuity_variance_gbp,
    corporate_continuity_exception_count,
    has_period_continuity_exception
from {{ ref('mart_deferred_revenue_control') }}
where (
        abs(corporate_continuity_variance_gbp) > 0.01
        and has_period_continuity_exception = false
      )
   or (
        abs(corporate_continuity_variance_gbp) <= 0.01
        and has_period_continuity_exception = true
      )
