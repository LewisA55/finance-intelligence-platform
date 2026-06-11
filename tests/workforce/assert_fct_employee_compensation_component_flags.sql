select *
from {{ ref('fct_employee_compensation') }}
where
    (
        case when is_base_salary then 1 else 0 end
        + case when is_employer_tax then 1 else 0 end
        + case when is_benefits then 1 else 0 end
        + case when is_bonus_accrual then 1 else 0 end
    ) <> 1
