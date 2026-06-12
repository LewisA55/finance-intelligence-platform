select *
from {{ ref('mart_workforce_cost_control') }}
where has_payroll_without_active_headcount = true
  and reporting_month_date between date '2022-01-01' and date '2026-12-01'
