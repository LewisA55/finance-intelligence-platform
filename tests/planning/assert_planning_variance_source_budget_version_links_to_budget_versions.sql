/*
Purpose:
    Ensure every variance source line budget version links to budget version governance.

Expected result:
    Zero rows.
*/

select
    v.variance_extract_pk,
    v.variance_extract_line_id,
    v.forecast_version_code,
    v.forecast_scenario,
    v.budget_version_code,
    v.posting_period
from {{ ref('stg_planning__variance_source_extract') }} as v
left join {{ ref('stg_planning__budget_versions') }} as bv
    on v.budget_version_code = bv.budget_version_code
where bv.budget_version_code is null
