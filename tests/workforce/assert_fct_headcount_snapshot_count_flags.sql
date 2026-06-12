select *
from {{ ref('fct_headcount_snapshot') }}
where active_headcount_count <> case when is_active then 1 else 0 end
   or ghost_headcount_count <> case when is_ghost_headcount then 1 else 0 end
   or active_fte_count <> case when is_active then fte_count else 0 end
   or ghost_fte_count <> case when is_ghost_headcount then fte_count else 0 end
