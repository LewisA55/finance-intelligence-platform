select *
from {{ ref('mart_workforce_cost_control') }}
where round(open_position_monthly_salary_exposure_gbp - open_position_annual_salary_exposure_gbp / 12, 2) <> 0
