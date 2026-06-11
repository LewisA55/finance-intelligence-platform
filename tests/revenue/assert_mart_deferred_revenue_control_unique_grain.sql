/*
    Test: mart_deferred_revenue_control grain is unique.

    Failure condition:
    More than one row exists for the declared corporate-period grain.
*/

select
    period_month_date_hk,
    period_status,
    currency_code,
    revenue_category,
    count(*) as row_count
from {{ ref('mart_deferred_revenue_control') }}
group by
    period_month_date_hk,
    period_status,
    currency_code,
    revenue_category
having count(*) > 1
