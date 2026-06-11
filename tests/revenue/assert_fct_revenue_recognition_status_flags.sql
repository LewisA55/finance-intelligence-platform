/*
    Test: fct_revenue_recognition status flags are mutually exclusive.

    Failure condition:
    A row is both actual and scheduled, or neither.
*/

select
    revenue_recognition_hk,
    recognition_id,
    recognition_status,
    is_actual_recognition,
    is_scheduled_recognition
from {{ ref('fct_revenue_recognition') }}
where (
        cast(is_actual_recognition as integer)
        + cast(is_scheduled_recognition as integer)
      ) <> 1
