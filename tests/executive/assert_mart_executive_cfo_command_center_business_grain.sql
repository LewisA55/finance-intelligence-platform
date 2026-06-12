select
    reporting_month_date_hk,
    reporting_scope,
    region_hk,
    business_unit_code,
    count(*) as row_count
from {{ ref('mart_executive_cfo_command_center') }}
group by 1, 2, 3, 4
having count(*) > 1
