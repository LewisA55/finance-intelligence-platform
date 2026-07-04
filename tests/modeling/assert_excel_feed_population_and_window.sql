-- The Excel feed must contain exactly the workbook's eligible population:
-- 42 unique months spanning Jan 2023 - Jun 2026, with no future period and
-- no month duplicated. Any row returned is a failure.
with checks as (

    select
        count(*) as row_count,
        count(distinct reporting_month_date) as distinct_months,
        min(reporting_month_date) as first_month,
        max(reporting_month_date) as last_month
    from {{ ref('mart_model_actuals_feed_excel') }}

)

select *
from checks
where row_count <> 42
   or distinct_months <> row_count
   or first_month <> date '2023-01-01'
   or last_month <> date '2026-06-01'
