select *
from {{ ref('mart_workforce_cost_control') }}
where round(
    payroll_cost_gbp
    - base_salary_cost_gbp
    - employer_tax_cost_gbp
    - benefits_cost_gbp
    - bonus_accrual_cost_gbp,
    2
) <> 0
