/*
Purpose:
    Ensure forecast lines preserve correct basis semantics:
      - Actualised months use actual source bases.
      - Future months use scenario driver forecast basis.

Expected result:
    Zero rows.
*/

select
    forecast_line_pk,
    forecast_line_id,
    forecast_version_code,
    scenario_type,
    posting_period,
    forecast_basis
from {{ ref('stg_planning__forecast_lines') }}
where
    (
        forecast_basis in ('ACTUAL_WORKFORCE_SUBLEDGER', 'ACTUAL_FS_ALLOCATED_TO_AOP_GRAIN')
        and posting_period > date '2026-03-01'
    )
    or
    (
        forecast_basis = 'SCENARIO_DRIVER_FORECAST'
        and posting_period <= date '2026-03-01'
    )
