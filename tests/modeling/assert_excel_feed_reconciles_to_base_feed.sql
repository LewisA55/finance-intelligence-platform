-- Every value the Excel feed carries must reconcile to its governed source
-- in mart_model_actuals_feed (billings to the deferred-additions basis, the
-- opex proxy to payroll + AP ahead of GL close, and profit to the
-- recognised-revenue basis). Any row returned is a failure.
select
    excel.reporting_month_date,
    excel.billings_gbp - base.deferred_revenue_additions_gbp as billings_variance,
    excel.recognised_revenue_actual_gbp - base.recognised_revenue_gbp as revenue_variance,
    excel.cash_collected_gbp - base.cash_collected_gbp as cash_variance,
    excel.open_ar_exposure_gbp - base.open_ar_gbp as ar_variance,
    excel.open_ap_liability_gbp - base.open_ap_gbp as ap_variance,
    excel.closing_deferred_revenue_gbp - base.closing_deferred_revenue_gbp as deferred_variance,
    excel.actual_operating_expense_gbp - case
        when base.has_financial_actuals then base.opex_gbp
        else base.payroll_cost_gbp + base.ap_spend_gbp
    end as opex_variance,
    excel.actual_operating_profit_gbp
        - (excel.recognised_revenue_actual_gbp - excel.actual_operating_expense_gbp) as profit_identity_variance
from {{ ref('mart_model_actuals_feed_excel') }} as excel
inner join {{ ref('mart_model_actuals_feed') }} as base
    on excel.reporting_month_date = base.reporting_month_date
   and base.reporting_scope = 'Company Total'
   and base.scenario_code = 'ACTUALS'
where abs(excel.billings_gbp - base.deferred_revenue_additions_gbp) > 0.01
   or abs(excel.recognised_revenue_actual_gbp - base.recognised_revenue_gbp) > 0.01
   or abs(excel.cash_collected_gbp - base.cash_collected_gbp) > 0.01
   or abs(excel.open_ar_exposure_gbp - base.open_ar_gbp) > 0.01
   or abs(excel.open_ap_liability_gbp - base.open_ap_gbp) > 0.01
   or abs(excel.closing_deferred_revenue_gbp - base.closing_deferred_revenue_gbp) > 0.01
   or abs(
        excel.actual_operating_expense_gbp - case
            when base.has_financial_actuals then base.opex_gbp
            else base.payroll_cost_gbp + base.ap_spend_gbp
        end
      ) > 0.01
   or abs(
        excel.actual_operating_profit_gbp
        - (excel.recognised_revenue_actual_gbp - excel.actual_operating_expense_gbp)
      ) > 0.01
