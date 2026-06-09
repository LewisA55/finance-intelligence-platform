/*
Purpose:
    Ensure every variance source line links back to a valid source budget line.

Expected result:
    Zero rows.
*/

select
    v.variance_extract_pk,
    v.variance_extract_line_id,
    v.forecast_version_code,
    v.forecast_scenario,
    v.budget_version_code,
    v.source_budget_line_id,
    v.posting_period
from {{ ref('stg_planning__variance_source_extract') }} as v
left join {{ ref('stg_planning__budget_lines') }} as bl
    on v.source_budget_line_id = bl.budget_line_id
   and v.budget_version_code = bl.budget_version_code
where bl.budget_line_id is null
