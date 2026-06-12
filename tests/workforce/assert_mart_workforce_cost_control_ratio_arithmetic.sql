select *
from {{ ref('mart_workforce_cost_control') }}
where
    round(
        payroll_cost_per_active_head_gbp
        - case when active_headcount_count > 0 then payroll_cost_gbp / active_headcount_count else 0 end,
        2
    ) <> 0

    or round(
        payroll_cost_per_active_fte_gbp
        - case when active_fte_count > 0 then payroll_cost_gbp / active_fte_count else 0 end,
        2
    ) <> 0

    or round(
        employer_tax_ratio
        - case when payroll_cost_gbp > 0 then employer_tax_cost_gbp / payroll_cost_gbp else 0 end,
        6
    ) <> 0

    or round(
        benefits_ratio
        - case when payroll_cost_gbp > 0 then benefits_cost_gbp / payroll_cost_gbp else 0 end,
        6
    ) <> 0

    or round(
        bonus_accrual_ratio
        - case when payroll_cost_gbp > 0 then bonus_accrual_cost_gbp / payroll_cost_gbp else 0 end,
        6
    ) <> 0
