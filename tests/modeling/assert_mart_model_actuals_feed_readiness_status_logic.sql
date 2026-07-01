select *
from {{ ref('mart_model_actuals_feed') }}
where (
        model_blocking_exception_count > 0
        and model_readiness_status <> 'Blocked'
    )
   or (
        model_blocking_exception_count = 0
        and review_exception_count > 0
        and model_readiness_status <> 'Usable with review'
    )
   or (
        model_blocking_exception_count = 0
        and review_exception_count = 0
        and accepted_limitation_exception_count > 0
        and model_readiness_status <> 'Accepted limitation'
    )
   or (
        total_control_exception_count = 0
        and model_readiness_status <> 'Ready'
    )
