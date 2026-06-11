/*
    Test: fct_deferred_revenue_rollforward period status flags are mutually exclusive.

    Failure condition:
    A row is both actual and scheduled, or neither.
*/

select
    deferred_revenue_rollforward_hk,
    rollforward_pk,
    period_status,
    is_actual_period,
    is_scheduled_period
from {{ ref('fct_deferred_revenue_rollforward') }}
where (
        cast(is_actual_period as integer)
        + cast(is_scheduled_period as integer)
      ) <> 1
