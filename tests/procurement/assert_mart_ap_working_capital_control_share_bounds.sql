/* Test: vendor concentration percentages remain within sensible bounds. */
select ap_working_capital_control_hk, vendor_hk, reporting_month_date,
       vendor_spend_share_percentage, vendor_payment_share_percentage, vendor_open_ap_share_percentage
from {{ ref('mart_ap_working_capital_control') }}
where vendor_spend_share_percentage < 0 or vendor_spend_share_percentage > 100
   or vendor_payment_share_percentage < 0 or vendor_payment_share_percentage > 100
   or vendor_open_ap_share_percentage < 0 or vendor_open_ap_share_percentage > 100
