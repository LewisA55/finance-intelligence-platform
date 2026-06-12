select *
from {{ ref('fct_headcount_snapshot') }}
where is_active_headcount <> is_active
   or is_inactive_headcount <> (not is_active)
   or is_active_status <> (lower(trim(employment_status)) = 'active')
   or is_terminated_status <> (lower(trim(employment_status)) = 'terminated')
   or is_status_active_mismatch <> (
        (lower(trim(employment_status)) = 'terminated' and is_active)
        or
        (lower(trim(employment_status)) = 'active' and not is_active)
   )
