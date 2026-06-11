/* Test: mart_revenue_waterfall grain is unique. */
select
    customer_hk,
    reporting_month_date_hk,
    currency_code,
    count(*) as row_count
from {{ ref('mart_revenue_waterfall') }}
group by
    customer_hk,
    reporting_month_date_hk,
    currency_code
having count(*) > 1
