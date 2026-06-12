select *
from {{ ref('fct_headcount_snapshot') }}
where snapshot_month_date <> last_day(snapshot_month_date)
   or not is_month_end_snapshot
