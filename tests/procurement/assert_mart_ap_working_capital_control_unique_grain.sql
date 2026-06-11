/* Test: mart_ap_working_capital_control business grain is unique. */
select vendor_hk, reporting_month_date_hk, reporting_month_date, count(*) as row_count
from {{ ref('mart_ap_working_capital_control') }}
group by vendor_hk, reporting_month_date_hk, reporting_month_date
having count(*) > 1
