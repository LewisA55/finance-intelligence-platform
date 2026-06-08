/*
Purpose:
    Ensure clean recognition day counts are positive and bounded by the full
    service-period day count.

Grain:
    One failing row per clean recognition schedule row with invalid day counts.

Expected result:
    Zero rows.
*/

select
    revenue_recognition_pk,
    recognition_id,
    invoice_id,
    invoice_line_id,
    days_in_service_period,
    days_recognised_in_month
from {{ ref('stg_revenue__revenue_recognition_schedule') }}
where
    is_defect = false
    and (
        days_in_service_period <= 0
        or days_recognised_in_month <= 0
        or days_recognised_in_month > days_in_service_period
    )
