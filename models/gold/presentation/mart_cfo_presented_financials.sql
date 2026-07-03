{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'mart', 'presentation', 'financial_performance']
) }}

/*
    Presented-basis financial performance.

    The warehouse deliberately retains as-found audit telemetry (synthetic
    source defects included) so the control layer has something to catch.
    This mart is the management presentation layer above it: every line
    carries both the as-found and the presented value, and anything the
    presentation policy excludes is disclosed, never hidden.

    Policy applied here: `source_completeness_expense` from the
    presentation_policy seed — expense lines with a material budget and
    almost no captured actuals read as missing source capture, not
    favourable underspend, and are excluded from the presented basis.
*/

with policy as (

    select *
    from {{ ref('presentation_policy') }}
    where policy_key = 'source_completeness_expense'

),

financials as (

    select *
    from {{ ref('mart_financial_performance') }}
    where forecast_version_code = 'FC_BASE_CASE'

),

classified as (

    select
        financials.financial_performance_hk,
        financials.posting_period,
        financials.fiscal_year,
        financials.period_status,
        financials.department_hk,
        financials.department_id,
        financials.account_code,
        financials.account_name,
        financials.account_class,
        financials.financial_statement,

        financials.actual_amount_gbp as as_found_actual_gbp,
        financials.budget_amount_gbp,
        financials.forecast_amount_gbp,
        financials.actual_vs_budget_variance_gbp as as_found_variance_gbp,
        financials.actual_vs_budget_favourability as as_found_favourability,

        (
            financials.account_class = 'Expense'
            and financials.actual_vs_budget_favourability = 'Favourable'
            and financials.budget_amount_gbp >= policy.threshold_gbp
            and financials.actual_amount_gbp < policy.threshold_ratio * financials.budget_amount_gbp
        ) as excluded_from_presentation_flag,

        policy.threshold_gbp as materiality_threshold_gbp,
        policy.treatment as policy_treatment,
        policy.disclosure_template as policy_disclosure

    from financials
    cross join policy

),

final as (

    select
        financial_performance_hk,
        posting_period,
        fiscal_year,
        period_status,
        department_hk,
        department_id,
        account_code,
        account_name,
        account_class,
        financial_statement,

        as_found_actual_gbp,
        budget_amount_gbp,
        forecast_amount_gbp,
        as_found_variance_gbp,
        as_found_favourability,

        excluded_from_presentation_flag,

        case
            when excluded_from_presentation_flag then null
            else as_found_actual_gbp
        end as presented_actual_gbp,

        case
            when excluded_from_presentation_flag then null
            else as_found_variance_gbp
        end as presented_variance_gbp,

        -- Actuals removed from the presented basis (zero when the line presents).
        case
            when excluded_from_presentation_flag then as_found_actual_gbp
            else 0
        end as adjustment_amount_gbp,

        case
            when excluded_from_presentation_flag then 'Excluded - source completeness'
            else 'Presented'
        end as presentation_basis_status,

        materiality_threshold_gbp,

        case
            when excluded_from_presentation_flag then policy_disclosure
            else null
        end as disclosure_text,

        case
            when excluded_from_presentation_flag then policy_treatment
            else 'Presented'
        end as control_treatment,

        'source_completeness_expense' as policy_key,

        current_timestamp as _atlas_modelled_at

    from classified

)

select *
from final
