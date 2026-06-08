/*
Purpose:
    Validate clean deferred revenue rollforward arithmetic.

Formula:
    opening deferred revenue
    + new billings deferred
    - recognised revenue
    = closing deferred revenue

Grain:
    One failing row per clean period / currency / revenue category rollforward
    where local or GBP arithmetic does not agree within tolerance.

Expected result:
    Zero rows.
*/

select
    rollforward_pk,
    period_month,
    period_status,
    currency,
    revenue_category,

    opening_deferred_revenue_local,
    new_billings_deferred_local,
    recognised_revenue_local,
    closing_deferred_revenue_local,
    round(
        opening_deferred_revenue_local
        + new_billings_deferred_local
        - recognised_revenue_local
        - closing_deferred_revenue_local,
        2
    ) as local_variance,

    opening_deferred_revenue_gbp,
    new_billings_deferred_gbp,
    recognised_revenue_gbp,
    closing_deferred_revenue_gbp,
    round(
        opening_deferred_revenue_gbp
        + new_billings_deferred_gbp
        - recognised_revenue_gbp
        - closing_deferred_revenue_gbp,
        2
    ) as gbp_variance

from {{ ref('stg_revenue__deferred_revenue_rollforward') }}
where
    is_defect = false
    and (
        abs(
            opening_deferred_revenue_local
            + new_billings_deferred_local
            - recognised_revenue_local
            - closing_deferred_revenue_local
        ) > 0.01
        or abs(
            opening_deferred_revenue_gbp
            + new_billings_deferred_gbp
            - recognised_revenue_gbp
            - closing_deferred_revenue_gbp
        ) > 0.01
    )
