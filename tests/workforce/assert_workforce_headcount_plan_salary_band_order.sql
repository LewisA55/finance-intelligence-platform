/*
Purpose:
    Ensure authorised headcount plan salary bands are ordered correctly:
    target_salary_low_local <= target_salary_mid_local <= target_salary_high_local.

Expected result:
    Zero rows.
*/

select
    position_pk,
    position_id,
    plan_status,
    currency,
    target_salary_low_local,
    target_salary_mid_local,
    target_salary_high_local
from {{ ref('stg_workforce__headcount_plan') }}
where target_salary_low_local > target_salary_mid_local
   or target_salary_mid_local > target_salary_high_local
