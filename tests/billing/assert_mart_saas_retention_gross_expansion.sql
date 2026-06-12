select *
from {{ ref('mart_saas_retention') }}
where round(gross_expansion_arr_gbp - expansion_arr_gbp - price_increase_arr_gbp, 2) <> 0
