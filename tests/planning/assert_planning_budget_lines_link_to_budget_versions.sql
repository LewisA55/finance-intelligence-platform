/*
Purpose:
    Ensure every budget line links to a valid locked budget version.

Expected result:
    Zero rows.
*/

select
    bl.budget_line_pk,
    bl.budget_line_id,
    bl.budget_version_code,
    bl.fiscal_year,
    bl.posting_period
from {{ ref('stg_planning__budget_lines') }} as bl
left join {{ ref('stg_planning__budget_versions') }} as bv
    on bl.budget_version_code = bv.budget_version_code
where bv.budget_version_code is null
