/*
Purpose:
    Ensure every forecast line links back to a valid source budget line.

Expected result:
    Zero rows.
*/

select
    fl.forecast_line_pk,
    fl.forecast_line_id,
    fl.forecast_version_code,
    fl.scenario_type,
    fl.source_budget_version_code,
    fl.source_budget_line_id,
    fl.posting_period
from {{ ref('stg_planning__forecast_lines') }} as fl
left join {{ ref('stg_planning__budget_lines') }} as bl
    on fl.source_budget_line_id = bl.budget_line_id
   and fl.source_budget_version_code = bl.budget_version_code
where bl.budget_line_id is null
