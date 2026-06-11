/*
    Test: clean fct_deferred_revenue_rollforward rows pass rollforward arithmetic.

    Failure condition:
    Any non-defect row has a non-zero rollforward variance.

    Note:
    Defect rows are preserved in the core fact and surfaced through
    is_rollforward_arithmetic_exception.
*/

select
    deferred_revenue_rollforward_hk,
    rollforward_pk,
    period_month,
    period_status,
    currency_code,
    revenue_category,
    rollforward_variance_local,
    rollforward_variance_gbp,
    is_defect,
    defect_type
from {{ ref('fct_deferred_revenue_rollforward') }}
where is_defect = false
  and (
        abs(rollforward_variance_local) > 0.01
     or abs(rollforward_variance_gbp) > 0.01
  )
