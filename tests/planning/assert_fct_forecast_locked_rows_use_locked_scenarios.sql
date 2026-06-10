/*
    Test: fct_forecast locked rows point to locked forecast scenarios.

    Failure condition:
    Any locked forecast line whose related forecast scenario is not locked.
*/

select
    f.forecast_line_id,
    f.forecast_version_code,
    f.forecast_scenario,
    f.is_locked as forecast_line_is_locked,
    d.is_locked as forecast_scenario_is_locked
from {{ ref('fct_forecast') }} as f
left join {{ ref('dim_forecast_scenario') }} as d
    on f.forecast_scenario_hk = d.forecast_scenario_hk
where f.is_locked = true
  and coalesce(d.is_locked, false) = false
