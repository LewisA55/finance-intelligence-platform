/* Test: AP exposure bucket arithmetic is internally consistent. */
select ap_working_capital_control_hk, vendor_hk, reporting_month_date,
       open_payable_liability_gbp, current_payable_liability_gbp, overdue_payable_liability_gbp,
       current_open_amount_gbp, one_to_thirty_overdue_gbp, thirty_one_to_sixty_overdue_gbp,
       sixty_one_to_ninety_overdue_gbp, ninety_plus_overdue_gbp
from {{ ref('mart_ap_working_capital_control') }}
where abs(open_payable_liability_gbp - current_payable_liability_gbp - overdue_payable_liability_gbp) > 0.01
   or abs(overdue_payable_liability_gbp - one_to_thirty_overdue_gbp - thirty_one_to_sixty_overdue_gbp - sixty_one_to_ninety_overdue_gbp - ninety_plus_overdue_gbp) > 0.01
