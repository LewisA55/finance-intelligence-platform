select *
from {{ ref('mart_saas_arr_movement') }}
where reporting_month_date <> cast(date_trunc('month', reporting_month_date) as date)
