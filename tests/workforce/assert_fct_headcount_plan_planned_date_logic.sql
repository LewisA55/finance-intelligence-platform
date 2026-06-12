select *
from {{ ref('fct_headcount_plan') }}
where
    (plan_status = 'ACTIVE' and planned_hire_date is not null)
    or (plan_status = 'ACTIVE' and planned_start_period is not null)
    or (plan_status in ('OPEN_BUDGETED', 'BACKFILL') and planned_hire_date is null)
    or (plan_status in ('OPEN_BUDGETED', 'BACKFILL') and planned_start_period is null)
    or (
        planned_hire_date is not null
        and planned_start_period is not null
        and planned_start_period < planned_hire_date
    )
