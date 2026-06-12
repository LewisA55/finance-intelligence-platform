select *
from {{ ref('mart_executive_cfo_command_center') }}
where reporting_month_date <> cast(date_trunc('month', reporting_month_date) as date)
