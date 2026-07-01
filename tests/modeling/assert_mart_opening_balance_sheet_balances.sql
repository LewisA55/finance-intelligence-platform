select *
from {{ ref('mart_opening_balance_sheet') }}
where abs(balance_check_variance_gbp) >= 0.01
   or not is_balanced
