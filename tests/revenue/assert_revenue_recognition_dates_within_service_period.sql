/*
Purpose:
    Ensure each clean recognition date window sits inside its invoice line
    service period.

Grain:
    One failing row per clean recognition schedule row whose recognition start
    or end date falls outside the service period, or whose recognition end date
    precedes its start date.

Expected result:
    Zero rows.
*/

select
    revenue_recognition_pk,
    recognition_id,
    invoice_id,
    invoice_line_id,
    recognition_month,
    service_period_start_date,
    service_period_end_date,
    recognition_start_date,
    recognition_end_date
from {{ ref('stg_revenue__revenue_recognition_schedule') }}
where
    is_defect = false
    and (
        recognition_start_date < service_period_start_date
        or recognition_end_date > service_period_end_date
        or recognition_end_date < recognition_start_date
    )
