/*
Purpose:
    Validate lifecycle logic for authorised workforce positions:
      - ACTIVE rows must have an assigned employee_id.
      - OPEN_BUDGETED and BACKFILL rows must not have an assigned employee_id.
      - OPEN_BUDGETED and BACKFILL rows must have planned hire/start dates.

Expected result:
    Zero rows.
*/

select
    position_pk,
    position_id,
    employee_id,
    plan_status,
    planned_hire_date,
    planned_start_period
from {{ ref('stg_workforce__headcount_plan') }}
where
    (
        plan_status = 'ACTIVE'
        and employee_id is null
    )
    or
    (
        plan_status in ('OPEN_BUDGETED', 'BACKFILL')
        and employee_id is not null
    )
    or
    (
        plan_status in ('OPEN_BUDGETED', 'BACKFILL')
        and (
            planned_hire_date is null
            or planned_start_period is null
        )
    )
