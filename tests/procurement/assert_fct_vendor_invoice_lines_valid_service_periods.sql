/*
    Test: fct_vendor_invoice_lines service periods are valid.

    Failure condition:
    Service period end date is before service period start date.
*/

select
    vendor_invoice_line_hk,
    vendor_invoice_line_id,
    service_period_start_date,
    service_period_end_date,
    is_invalid_service_period
from {{ ref('fct_vendor_invoice_lines') }}
where is_invalid_service_period = true
