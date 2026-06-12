select *
from {{ ref('fct_headcount_plan') }}
where target_salary_low_local > target_salary_mid_local
   or target_salary_mid_local > target_salary_high_local
   or target_salary_mid_gbp <= 0
   or fx_rate_to_gbp <= 0
