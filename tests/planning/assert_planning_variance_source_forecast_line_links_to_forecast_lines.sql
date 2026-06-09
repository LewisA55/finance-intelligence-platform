/*
Purpose:
    Ensure every variance source line links back to a valid forecast line.

Expected result:
    Zero rows.
*/

select
    v.variance_extract_pk,
    v.variance_extract_line_id,
    v.forecast_version_code,
    v.forecast_scenario,
    v.source_forecast_line_id,
    v.posting_period
from {{ ref('stg_planning__variance_source_extract') }} as v
left join {{ ref('stg_planning__forecast_lines') }} as fl
    on v.source_forecast_line_id = fl.forecast_line_id
   and v.forecast_version_code = fl.forecast_version_code
where fl.forecast_line_id is null
