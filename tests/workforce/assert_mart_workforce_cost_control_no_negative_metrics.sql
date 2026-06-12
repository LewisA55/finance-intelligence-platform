select *
from {{ ref('mart_workforce_cost_control') }}
where payroll_cost_gbp < 0
   or base_salary_cost_gbp < 0
   or employer_tax_cost_gbp < 0
   or benefits_cost_gbp < 0
   or bonus_accrual_cost_gbp < 0
   or active_headcount_count < 0
   or fte_count < 0
   or active_fte_count < 0
   or monthly_salary_exposure_gbp < 0
   or ghost_monthly_salary_exposure_gbp < 0
   or open_position_annual_salary_exposure_gbp < 0
   or open_position_monthly_salary_exposure_gbp < 0
