select *
from {{ ref('fct_headcount_plan') }}
where
    (
        case when is_active_position then 1 else 0 end
        + case when is_open_budgeted_position then 1 else 0 end
        + case when is_backfill_position then 1 else 0 end
    ) <> 1
    or is_open_position <> (plan_status in ('OPEN_BUDGETED', 'BACKFILL'))
    or is_filled_position <> (
        plan_status = 'ACTIVE'
        and employee_id is not null
        and trim(employee_id) <> ''
    )
    or is_growth_position <> (not is_backfill)
