{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'mart', 'modelling', 'balance_sheet', 'three_statement_model']
) }}

with source as (

    select *
    from {{ ref('stg_accounting__opening_balance_sheet') }}

),

final as (

    select
        md5(strftime(as_of_date, '%Y-%m-%d')) as opening_balance_sheet_hk,
        md5(strftime(as_of_date, '%Y-%m-%d')) as as_of_date_hk,
        as_of_date,

        cash_gbp,
        accounts_receivable_gbp,
        prepaids_other_current_assets_gbp,
        ppe_gbp,
        accumulated_depreciation_gbp,
        ppe_gbp + accumulated_depreciation_gbp as net_ppe_gbp,

        cash_gbp
        + accounts_receivable_gbp
        + prepaids_other_current_assets_gbp as total_current_assets_gbp,

        cash_gbp
        + accounts_receivable_gbp
        + prepaids_other_current_assets_gbp
        + ppe_gbp
        + accumulated_depreciation_gbp as total_assets_gbp,

        accounts_payable_gbp,
        deferred_revenue_gbp,
        debt_gbp,

        accounts_payable_gbp
        + deferred_revenue_gbp
        + debt_gbp as total_liabilities_gbp,

        share_capital_gbp,
        retained_earnings_gbp,
        share_capital_gbp + retained_earnings_gbp as total_equity_gbp,

        (
            cash_gbp
            + accounts_receivable_gbp
            + prepaids_other_current_assets_gbp
            + ppe_gbp
            + accumulated_depreciation_gbp
        )
        - (
            accounts_payable_gbp
            + deferred_revenue_gbp
            + debt_gbp
            + share_capital_gbp
            + retained_earnings_gbp
        ) as balance_check_variance_gbp,

        abs(
            (
                cash_gbp
                + accounts_receivable_gbp
                + prepaids_other_current_assets_gbp
                + ppe_gbp
                + accumulated_depreciation_gbp
            )
            - (
                accounts_payable_gbp
                + deferred_revenue_gbp
                + debt_gbp
                + share_capital_gbp
                + retained_earnings_gbp
            )
        ) < 0.01 as is_balanced,

        source_system,
        model_note,
        current_timestamp as _atlas_modelled_at

    from source

)

select *
from final
