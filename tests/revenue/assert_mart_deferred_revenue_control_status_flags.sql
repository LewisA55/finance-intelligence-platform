/*
    Test: mart_deferred_revenue_control period status flags are mutually exclusive.

    Failure condition:
    A row is both actual and scheduled, or neither.
*/

select
    deferred_revenue_control_hk,
    period_month,
    period_status,
    is_actual_period,
    is_scheduled_period
from {{ ref('mart_deferred_revenue_control') }}
where (
        cast(is_actual_period as integer)
        + cast(is_scheduled_period as integer)
      ) <> 1
