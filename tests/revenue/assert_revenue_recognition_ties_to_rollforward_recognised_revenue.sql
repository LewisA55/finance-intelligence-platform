/*
Purpose:
    Reconcile clean deferred revenue rollforward recognised revenue to the
    detailed revenue recognition schedule by month, currency, and revenue
    category.

Grain:
    One failing row per clean rollforward period_month / currency /
    revenue_category where the detailed schedule total does not agree to the
    rollforward recognised revenue total within tolerance.

Expected result:
    Zero rows.

Notes:
    This control is driven from clean rollforward rows. If a rollforward row is
    intentionally defect-flagged, it is excluded from this clean accounting
    tie-out and should be surfaced separately in a control / exception mart.

    The detailed schedule is included in full because the rollforward is an
    aggregate accounting output produced from the recognition schedule.
*/

with schedule_recognition as (

    select
        recognition_month as period_month,
        currency,
        revenue_category,
        round(sum(recognised_revenue_local), 2) as schedule_recognised_revenue_local,
        round(sum(recognised_revenue_gbp), 2) as schedule_recognised_revenue_gbp
    from {{ ref('stg_revenue__revenue_recognition_schedule') }}
    group by
        recognition_month,
        currency,
        revenue_category

),

clean_rollforward_recognition as (

    select
        period_month,
        currency,
        revenue_category,
        round(sum(recognised_revenue_local), 2) as rollforward_recognised_revenue_local,
        round(sum(recognised_revenue_gbp), 2) as rollforward_recognised_revenue_gbp
    from {{ ref('stg_revenue__deferred_revenue_rollforward') }}
    where is_defect = false
    group by
        period_month,
        currency,
        revenue_category

)

select
    clean_rollforward_recognition.period_month,
    clean_rollforward_recognition.currency,
    clean_rollforward_recognition.revenue_category,

    coalesce(schedule_recognition.schedule_recognised_revenue_local, 0) as schedule_recognised_revenue_local,
    clean_rollforward_recognition.rollforward_recognised_revenue_local,
    round(
        coalesce(schedule_recognition.schedule_recognised_revenue_local, 0)
        - clean_rollforward_recognition.rollforward_recognised_revenue_local,
        2
    ) as local_variance,

    coalesce(schedule_recognition.schedule_recognised_revenue_gbp, 0) as schedule_recognised_revenue_gbp,
    clean_rollforward_recognition.rollforward_recognised_revenue_gbp,
    round(
        coalesce(schedule_recognition.schedule_recognised_revenue_gbp, 0)
        - clean_rollforward_recognition.rollforward_recognised_revenue_gbp,
        2
    ) as gbp_variance

from clean_rollforward_recognition
left join schedule_recognition
    on clean_rollforward_recognition.period_month = schedule_recognition.period_month
    and clean_rollforward_recognition.currency = schedule_recognition.currency
    and clean_rollforward_recognition.revenue_category = schedule_recognition.revenue_category

where
    abs(
        coalesce(schedule_recognition.schedule_recognised_revenue_local, 0)
        - clean_rollforward_recognition.rollforward_recognised_revenue_local
    ) > 0.01
    or abs(
        coalesce(schedule_recognition.schedule_recognised_revenue_gbp, 0)
        - clean_rollforward_recognition.rollforward_recognised_revenue_gbp
    ) > 0.01