/*
Purpose:
    Ensure variance source forecast version code and scenario label remain aligned.

Expected result:
    Zero rows.
*/

select
    forecast_version_code,
    forecast_scenario,
    count(*) as row_count
from {{ ref('stg_planning__variance_source_extract') }}
where
    (forecast_version_code = 'FC_BASE_CASE' and forecast_scenario != 'Base Case')
    or (forecast_version_code = 'FC_UPSIDE_CASE' and forecast_scenario != 'Upside Case')
    or (forecast_version_code = 'FC_DOWNSIDE_CASE' and forecast_scenario != 'Downside Case')
group by
    forecast_version_code,
    forecast_scenario
