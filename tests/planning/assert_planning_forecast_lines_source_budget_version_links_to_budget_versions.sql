/*
Purpose:
    Ensure every forecast line source budget version links to budget version governance.

Expected result:
    Zero rows.
*/

select
    fl.forecast_line_pk,
    fl.forecast_line_id,
    fl.forecast_version_code,
    fl.scenario_type,
    fl.source_budget_version_code,
    fl.posting_period
from {{ ref('stg_planning__forecast_lines') }} as fl
left join {{ ref('stg_planning__budget_versions') }} as bv
    on fl.source_budget_version_code = bv.budget_version_code
where bv.budget_version_code is null
