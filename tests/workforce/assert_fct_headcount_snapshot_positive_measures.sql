select *
from {{ ref('fct_headcount_snapshot') }}
where monthly_salary_local <= 0
   or monthly_salary_gbp <= 0
   or fte_count <= 0
   or active_fte_count < 0
   or ghost_fte_count < 0
   or active_headcount_count < 0
   or ghost_headcount_count < 0
