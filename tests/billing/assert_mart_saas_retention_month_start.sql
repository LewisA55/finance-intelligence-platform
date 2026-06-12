select *
from {{ ref('mart_saas_retention') }}
where reporting_month_date <> cast(date_trunc('month', reporting_month_date) as date)
