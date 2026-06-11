/* Test: mart_revenue_waterfall lifecycle flags are mutually exclusive. */
select
    revenue_waterfall_hk,
    customer_hk,
    reporting_month,
    currency_code,
    has_billing,
    has_recognition,
    is_billing_only,
    is_recognition_only,
    is_billing_and_recognition
from {{ ref('mart_revenue_waterfall') }}
where (
        cast(is_billing_only as integer)
        + cast(is_recognition_only as integer)
        + cast(is_billing_and_recognition as integer)
      ) <> 1
