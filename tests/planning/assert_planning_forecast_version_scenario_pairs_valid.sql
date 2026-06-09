/*
Purpose:
    Ensure forecast version code and scenario label remain aligned.

Expected result:
    Zero rows.
*/

select
    forecast_version_code,
    scenario_type,
    count(*) as row_count
from {{ ref('stg_planning__forecast_lines') }}
where
    (forecast_version_code = 'FC_BASE_CASE' and scenario_type != 'Base Case')
    or (forecast_version_code = 'FC_UPSIDE_CASE' and scenario_type != 'Upside Case')
    or (forecast_version_code = 'FC_DOWNSIDE_CASE' and scenario_type != 'Downside Case')
group by
    forecast_version_code,
    scenario_type
