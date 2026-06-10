/*
    Test: fct_budget locked rows point to locked budget versions.

    Grain checked:
    budget_line_id

    Failure condition:
    Any locked budget line whose related budget version is not locked.

    This protects the semantic consistency between the budget fact and the
    governed budget-version dimension.
*/

select
    b.budget_line_id,
    b.budget_version_code,
    b.is_locked as budget_line_is_locked,
    d.is_locked as budget_version_is_locked
from {{ ref('fct_budget') }} as b
left join {{ ref('dim_budget_version') }} as d
    on b.budget_version_hk = d.budget_version_hk
where b.is_locked = true
  and coalesce(d.is_locked, false) = false
