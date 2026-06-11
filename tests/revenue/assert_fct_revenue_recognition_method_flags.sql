/*
    Test: fct_revenue_recognition recognition method flags are mutually exclusive.

    Failure condition:
    A row is both daily pro-rata and point-in-time, or neither.
*/

select
    revenue_recognition_hk,
    recognition_id,
    recognition_method,
    is_daily_pro_rata_recognition,
    is_point_in_time_recognition
from {{ ref('fct_revenue_recognition') }}
where (
        cast(is_daily_pro_rata_recognition as integer)
        + cast(is_point_in_time_recognition as integer)
      ) <> 1
