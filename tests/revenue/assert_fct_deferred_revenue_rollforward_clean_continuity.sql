/*
    Test: clean fct_deferred_revenue_rollforward rows pass period continuity.

    Failure condition:
    A non-defect row has an opening balance that does not agree to the prior
    period closing balance for the same currency and revenue category, where
    the prior row is also non-defect.

    Note:
    Defect rows are preserved in the core fact and surfaced through
    is_period_continuity_exception. Rows immediately following a defect row may
    inherit a continuity variance from the defective prior closing balance and
    should not hard-fail this clean continuity assertion.
*/

with base as (

    select
        deferred_revenue_rollforward_hk,
        rollforward_pk,
        period_month,
        period_status,
        currency_code,
        revenue_category,
        opening_deferred_revenue_local,
        opening_deferred_revenue_gbp,
        closing_deferred_revenue_local,
        closing_deferred_revenue_gbp,
        continuity_variance_local,
        continuity_variance_gbp,
        is_defect,
        defect_type,

        lag(is_defect) over (
            partition by currency_code, revenue_category
            order by period_month
        ) as prior_is_defect

    from {{ ref('fct_deferred_revenue_rollforward') }}

)

select
    deferred_revenue_rollforward_hk,
    rollforward_pk,
    period_month,
    period_status,
    currency_code,
    revenue_category,
    continuity_variance_local,
    continuity_variance_gbp,
    is_defect,
    defect_type,
    prior_is_defect
from base
where is_defect = false
  and coalesce(prior_is_defect, false) = false
  and (
        abs(continuity_variance_local) > 0.01
     or abs(continuity_variance_gbp) > 0.01
  )