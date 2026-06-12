select
    reporting_month_date_hk,
    customer_hk,
    region_hk,
    product_id,
    customer_segment,
    count(*) as row_count
from {{ ref('mart_saas_arr_movement') }}
group by 1, 2, 3, 4, 5
having count(*) > 1
