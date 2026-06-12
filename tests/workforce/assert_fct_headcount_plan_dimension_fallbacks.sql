with unassigned_date as (

    select date_hk as unassigned_date_hk
    from {{ ref('dim_date') }}
    where is_unassigned = true

)

select plan_fact.*
from {{ ref('fct_headcount_plan') }} as plan_fact
cross join unassigned_date
where plan_fact.department_hk = md5('UNASSIGNED')
   or plan_fact.region_hk = md5('UNASSIGNED')

   -- Date fallbacks are allowed only where the source dates are intentionally missing.
   or (
        plan_fact.planned_hire_date is not null
        and plan_fact.planned_hire_date_hk = unassigned_date.unassigned_date_hk
   )

   or (
        plan_fact.planned_start_period is not null
        and plan_fact.planned_start_period_date_hk = unassigned_date.unassigned_date_hk
   )