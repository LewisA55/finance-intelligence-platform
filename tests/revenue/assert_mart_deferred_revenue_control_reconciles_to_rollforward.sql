/*
    Test: mart_deferred_revenue_control reconciles to fct_deferred_revenue_rollforward.

    Failure condition:
    Corporate GBP balances or row counts in the mart do not agree to the
    underlying deferred revenue rollforward fact.
*/

with mart_totals as (

    select
        count(*) as mart_rows,
        sum(rollforward_row_count) as mart_rollforward_rows,
        round(sum(corporate_opening_deferred_revenue_gbp), 2) as mart_opening_gbp,
        round(sum(corporate_new_billings_deferred_gbp), 2) as mart_new_billings_gbp,
        round(sum(corporate_recognised_revenue_gbp), 2) as mart_recognised_gbp,
        round(sum(corporate_closing_deferred_revenue_gbp), 2) as mart_closing_gbp,
        round(sum(corporate_rollforward_variance_gbp), 2) as mart_rollforward_variance_gbp,
        round(sum(corporate_continuity_variance_gbp), 2) as mart_continuity_variance_gbp
    from {{ ref('mart_deferred_revenue_control') }}

),

fact_totals as (

    select
        count(*) as fact_rollforward_rows,
        round(sum(opening_deferred_revenue_gbp), 2) as fact_opening_gbp,
        round(sum(new_billings_deferred_gbp), 2) as fact_new_billings_gbp,
        round(sum(recognised_revenue_gbp), 2) as fact_recognised_gbp,
        round(sum(closing_deferred_revenue_gbp), 2) as fact_closing_gbp,
        round(sum(rollforward_variance_gbp), 2) as fact_rollforward_variance_gbp,
        round(sum(continuity_variance_gbp), 2) as fact_continuity_variance_gbp
    from {{ ref('fct_deferred_revenue_rollforward') }}

)

select *
from mart_totals
cross join fact_totals
where mart_rollforward_rows <> fact_rollforward_rows
   or abs(mart_opening_gbp - fact_opening_gbp) > 0.01
   or abs(mart_new_billings_gbp - fact_new_billings_gbp) > 0.01
   or abs(mart_recognised_gbp - fact_recognised_gbp) > 0.01
   or abs(mart_closing_gbp - fact_closing_gbp) > 0.01
   or abs(mart_rollforward_variance_gbp - fact_rollforward_variance_gbp) > 0.01
   or abs(mart_continuity_variance_gbp - fact_continuity_variance_gbp) > 0.01
