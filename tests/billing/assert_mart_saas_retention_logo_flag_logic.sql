select *
from {{ ref('mart_saas_retention') }}
where beginning_active_customer_count not in (0, 1)
   or ending_active_customer_count not in (0, 1)
   or retained_customer_count not in (0, 1)
   or churned_customer_count not in (0, 1)
   or paused_customer_count not in (0, 1)
   or new_customer_count not in (0, 1)
   or cast(is_beginning_active_customer as integer) <> beginning_active_customer_count
   or cast(is_ending_active_customer as integer) <> ending_active_customer_count
   or cast(is_retained_customer as integer) <> retained_customer_count
   or cast(is_churned_customer as integer) <> churned_customer_count
   or cast(is_paused_customer as integer) <> paused_customer_count
   or cast(is_new_customer as integer) <> new_customer_count
   or (is_retained_customer and not is_beginning_active_customer)
   or (is_churned_customer and not is_beginning_active_customer)
   or (is_paused_customer and not is_beginning_active_customer)
   or (is_new_customer and is_beginning_active_customer)
