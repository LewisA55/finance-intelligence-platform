/*
Purpose:
    Ensure budget line posting periods sit within their governing budget version planning window.

Expected result:
    Zero rows.
*/

select
    bl.budget_line_pk,
    bl.budget_line_id,
    bl.budget_version_code,
    bl.posting_period,
    bv.planning_start_period,
    bv.planning_end_period
from {{ ref('stg_planning__budget_lines') }} as bl
inner join {{ ref('stg_planning__budget_versions') }} as bv
    on bl.budget_version_code = bv.budget_version_code
where bl.posting_period < bv.planning_start_period
   or bl.posting_period > bv.planning_end_period
