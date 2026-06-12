select *
from {{ ref('mart_executive_cfo_command_center') }}
where invoice_count < 0
   or subscription_count < 0
   or active_subscription_count < 0
   or beginning_active_customer_count < 0
   or retained_customer_count < 0
   or churned_customer_count < 0
   or active_headcount_count < 0
   or active_fte_count < 0
   or open_position_count < 0
   or financial_defect_row_count < 0
   or defective_invoice_count < 0
   or ap_control_exception_count < 0
   or workforce_control_issue_count < 0
   or saas_arr_control_issue_count < 0
   or saas_retention_control_issue_count < 0
