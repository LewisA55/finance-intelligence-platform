/* Test: mart_revenue_waterfall reconciles to fct_revenue_recognition. */
with mart_totals as (
    select
        round(sum(recognised_revenue_total_gbp), 2) as mart_recognised_revenue_gbp,
        sum(recognition_row_count) as mart_recognition_row_count,
        sum(actual_recognition_row_count) as mart_actual_recognition_row_count,
        sum(scheduled_recognition_row_count) as mart_scheduled_recognition_row_count
    from {{ ref('mart_revenue_waterfall') }}
),
fact_totals as (
    select
        round(sum(coalesce(recognised_revenue_gbp, 0)), 2) as fact_recognised_revenue_gbp,
        count(*) as fact_recognition_row_count,
        sum(case when is_actual_recognition then 1 else 0 end) as fact_actual_recognition_row_count,
        sum(case when is_scheduled_recognition then 1 else 0 end) as fact_scheduled_recognition_row_count
    from {{ ref('fct_revenue_recognition') }}
)
select
    mart_recognised_revenue_gbp,
    fact_recognised_revenue_gbp,
    mart_recognition_row_count,
    fact_recognition_row_count,
    mart_actual_recognition_row_count,
    fact_actual_recognition_row_count,
    mart_scheduled_recognition_row_count,
    fact_scheduled_recognition_row_count
from mart_totals
cross join fact_totals
where abs(mart_recognised_revenue_gbp - fact_recognised_revenue_gbp) > 0.01
   or mart_recognition_row_count <> fact_recognition_row_count
   or mart_actual_recognition_row_count <> fact_actual_recognition_row_count
   or mart_scheduled_recognition_row_count <> fact_scheduled_recognition_row_count
