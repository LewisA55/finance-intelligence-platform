select *
from {{ ref('fct_employee_compensation') }}
where
    (compensation_component = 'BASE_SALARY' and component_rate <> 1)
    or (compensation_component = 'EMPLOYER_TAX' and component_rate <= 0)
    or (compensation_component = 'BENEFITS' and component_rate <= 0)
    or (compensation_component = 'BONUS_ACCRUAL' and component_rate <= 0)
