{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'mart', 'presentation', 'metric_readiness']
) }}

/*
    Metric-level presentation readiness registry.

    One row per CFO metric: how much of its history presents cleanly, what
    was excluded or disclosed, and under which policy. This is the surface a
    reviewer (or the portal's Data & Validation page) reads to know whether a
    metric can be shown, caveated, or should be withheld.
*/

with metrics as (

    select
        *,
        -- A coalesced zero is not coverage: flows/counts only carry signal
        -- when non-zero; ratio metrics carry signal whenever non-null.
        presented_value is not null
            and (unit = 'ratio' or presented_value != 0) as has_signal
    from {{ ref('mart_cfo_presented_operating_metrics') }}

),

final as (

    select
        metric_code,
        max(metric_name) as metric_name,
        max(unit) as unit,

        count(*) as months_total,
        count(presented_value) as months_presented,
        sum(case when has_signal then 1 else 0 end) as months_with_signal,
        sum(case when excluded_from_presentation_flag then 1 else 0 end) as months_excluded,
        sum(case when disclosure_text is not null then 1 else 0 end) as months_with_disclosure,

        min(case when has_signal then reporting_month_date end) as coverage_from,
        max(case when has_signal then reporting_month_date end) as coverage_to,

        string_agg(distinct policy_key, '; ' order by policy_key) as policy_keys,
        max(disclosure_text) as disclosure_text,

        case
            when sum(case when excluded_from_presentation_flag then 1 else 0 end) > 0
                then 'Presented with exclusions'
            when sum(case when disclosure_text is not null then 1 else 0 end) > 0
                then 'Presented with disclosure'
            else 'Presented'
        end as presentation_basis_status,

        current_timestamp as _atlas_modelled_at

    from metrics
    group by metric_code

)

select *
from final
