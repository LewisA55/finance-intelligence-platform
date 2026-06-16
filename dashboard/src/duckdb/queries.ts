import { runQuery } from './client';
import type {
  ReportingMonth,
  CommandCenterKpis,
  RevenueTrendPoint,
  ValidationInfo,
  ExecutiveMonth,
  FinancialSummary,
  DepartmentVariance,
  AccountVariance,
  WorkingCapitalPosition,
  ArCollectionsPoint,
  ApAgeing,
  VendorAp,
  ControlSummary,
  SaasKpis,
  ArrWalk,
  RegionArr,
  ProductSegmentArr,
  ProductMovement,
  SegmentRetention,
  RevenueKpis,
  RevRecMonth,
  ArCustomer,
  ArCollection,
} from '../types';

// ---------------------------------------------------------------------------
// Semantic guardrail
// ---------------------------------------------------------------------------
// mart_executive_cfo_command_center mixes three reporting scopes:
//   'Company Total' | 'Region Total' | 'Business Unit Total'
// These MUST NOT be summed together or executive KPIs double-count. Every
// company-level query below hard-filters reporting_scope = 'Company Total'.
const COMPANY_TOTAL = `reporting_scope = 'Company Total'`;

/** Guard: month identifiers come from our own month list, but validate anyway. */
function assertMonthIso(monthIso: string): void {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(monthIso)) {
    throw new Error(`Invalid month_iso: ${monthIso}`);
  }
}

/** All Company-Total reporting months, flagged for actuals/SaaS availability. */
export async function getReportingMonths(): Promise<ReportingMonth[]> {
  return runQuery<ReportingMonth>(`
    select
      reporting_month_date::varchar              as month_iso,
      strftime(reporting_month_date, '%b %Y')    as month_label,
      (actual_revenue_gbp > 0)                   as has_actuals,
      (active_arr_gbp > 0)                        as has_saas
    from mart_executive_cfo_command_center
    where ${COMPANY_TOTAL}
    order by reporting_month_date
  `);
}

/** Company-Total KPI snapshot for one month. */
export async function getCommandCenterKpis(
  monthIso: string,
): Promise<CommandCenterKpis | null> {
  assertMonthIso(monthIso);
  const rows = await runQuery<CommandCenterKpis>(`
    select
      reporting_month_date::varchar                                   as month_iso,
      strftime(reporting_month_date, '%b %Y')                         as month_label,
      actual_revenue_gbp::double                                      as actual_revenue,
      budget_revenue_gbp::double                                      as budget_revenue,
      forecast_revenue_gbp::double                                    as forecast_revenue,
      actual_expense_gbp::double                                      as actual_expense,
      budget_expense_gbp::double                                      as budget_expense,
      forecast_expense_gbp::double                                    as forecast_expense,
      actual_operating_result_gbp::double                            as operating_result,
      (budget_revenue_gbp - budget_expense_gbp)::double               as budget_operating_result,
      (forecast_revenue_gbp - forecast_expense_gbp)::double           as forecast_operating_result,
      case when actual_revenue_gbp > 0
           then actual_operating_result_gbp / actual_revenue_gbp end::double as operating_margin,
      active_arr_gbp::double                                          as active_arr,
      active_mrr_gbp::double                                          as active_mrr,
      net_revenue_retention_rate::double                             as nrr,
      open_ar_exposure_gbp::double                                    as open_ar,
      open_ap_liability_gbp::double                                   as open_ap,
      net_ar_less_ap_exposure_gbp::double                            as net_working_capital,
      operational_cash_pressure_gbp::double                          as cash_pressure,
      payroll_cost_gbp::double                                        as payroll_cost,
      active_headcount_count::integer                                as headcount,
      ending_active_customer_count::integer                          as active_customers,
      revenue_governance_exception_count::integer                    as revenue_governance_exceptions,
      deferred_revenue_control_exception_count::integer              as deferred_exceptions,
      has_any_executive_control_issue                                as has_control_issue,
      (
        cast(has_financial_performance_control_issue as int)
        + cast(has_o2c_control_issue as int)
        + cast(has_revenue_control_issue as int)
        + cast(has_deferred_revenue_control_issue as int)
        + cast(has_ap_control_issue as int)
        + cast(has_workforce_control_issue as int)
        + cast(has_saas_control_issue as int)
      )::integer                                                      as control_issue_domains
    from mart_executive_cfo_command_center
    where ${COMPANY_TOTAL}
      and reporting_month_date = date '${monthIso}'
  `);
  return rows[0] ?? null;
}

/**
 * Actual vs budget vs forecast revenue by month (Company Total).
 * Actual is null after the last closed actuals month so the line stops cleanly
 * rather than dropping to zero.
 */
export async function getRevenueTrend(): Promise<RevenueTrendPoint[]> {
  return runQuery<RevenueTrendPoint>(`
    select
      strftime(reporting_month_date, '%b %Y')                         as month_label,
      reporting_month_date::varchar                                   as month_iso,
      case when actual_revenue_gbp > 0 then actual_revenue_gbp end::double as actual_revenue,
      budget_revenue_gbp::double                                      as budget_revenue,
      forecast_revenue_gbp::double                                    as forecast_revenue
    from mart_executive_cfo_command_center
    where ${COMPANY_TOTAL}
    order by reporting_month_date
  `);
}

/** Audit facts for the validation page. */
export async function getValidationInfo(): Promise<ValidationInfo> {
  const tables = (
    await runQuery<{ table_name: string }>(`
      select table_name
      from information_schema.tables
      where table_schema = 'main'
      order by table_name
    `)
  ).map((r) => r.table_name);

  const scopeCounts = await runQuery<{ reporting_scope: string; rows: number }>(`
    select reporting_scope, count(*)::integer as rows
    from mart_executive_cfo_command_center
    group by reporting_scope
    order by reporting_scope
  `);

  const summary = (
    await runQuery<{
      exec_rows: number;
      latest_month: string;
      latest_actuals: string | null;
      company_total_rows: number;
    }>(`
      select
        count(*)::integer                                          as exec_rows,
        max(reporting_month_date)::varchar                         as latest_month,
        max(case when actual_revenue_gbp > 0 then reporting_month_date end)::varchar as latest_actuals,
        sum(case when ${COMPANY_TOTAL} then 1 else 0 end)::integer as company_total_rows
      from mart_executive_cfo_command_center
    `)
  )[0];

  return {
    tables,
    execMartRowCount: summary.exec_rows,
    scopeCounts,
    latestReportingMonth: summary.latest_month,
    latestActualsMonth: summary.latest_actuals,
    companyTotalRowCount: summary.company_total_rows,
  };
}

/** Provenance for the management-pack header (built date, as-of month). */
export async function getDataAsAt(): Promise<{
  latest_actuals_month: string | null;
  latest_reporting_month: string;
  built_date: string | null;
}> {
  const rows = await runQuery<{
    latest_actuals_month: string | null;
    latest_reporting_month: string;
    built_date: string | null;
  }>(`
    select
      max(case when actual_revenue_gbp > 0 then reporting_month_date end)::varchar as latest_actuals_month,
      max(reporting_month_date)::varchar                                           as latest_reporting_month,
      strftime(max(_atlas_modelled_at), '%Y-%m-%d')                               as built_date
    from mart_executive_cfo_command_center
    where ${COMPANY_TOTAL}
  `);
  return rows[0];
}

/** SaaS KPI snapshot for the latest month with SaaS data (Company Total). */
export async function getSaasKpis(): Promise<SaasKpis | null> {
  const rows = await runQuery<SaasKpis>(`
    select
      strftime(reporting_month_date, '%b %Y')        as month_label,
      reporting_month_date::varchar                  as month_iso,
      active_arr_gbp::double                          as active_arr,
      active_mrr_gbp::double                          as active_mrr,
      net_revenue_retention_rate::double             as nrr,
      gross_revenue_retention_rate::double           as grr,
      logo_retention_rate::double                    as logo_retention,
      logo_churn_rate::double                         as logo_churn,
      net_arr_delta_gbp::double                       as net_arr_delta,
      new_customer_count::int                        as new_customers,
      churned_customer_count::int                    as churned_customers,
      paused_customer_count::int                     as paused_customers,
      retained_customer_count::int                   as retained_customers,
      beginning_active_customer_count::int           as beginning_customers,
      ending_active_customer_count::int              as ending_customers,
      subscription_count::int                        as subscriptions,
      active_subscription_count::int                 as active_subscriptions
    from mart_executive_cfo_command_center
    where ${COMPANY_TOTAL} and active_arr_gbp > 0
    order by reporting_month_date desc
    limit 1
  `);
  return rows[0] ?? null;
}

/** Period ARR walk: opening (first month) + movement totals = closing (last month). */
export async function getArrWalk(): Promise<ArrWalk | null> {
  const rows = await runQuery<ArrWalk>(`
    with m as (
      select * from mart_executive_cfo_command_center
      where ${COMPANY_TOTAL} and active_arr_gbp > 0
    )
    select
      (select beginning_arr_gbp from m order by reporting_month_date limit 1)::double      as opening,
      sum(new_business_arr_gbp)::double                                                    as new_business,
      sum(expansion_arr_gbp)::double                                                       as expansion,
      sum(price_increase_arr_gbp)::double                                                  as price_increase,
      sum(contraction_arr_gbp)::double                                                     as contraction,
      sum(churn_arr_gbp)::double                                                           as churn,
      sum(pause_arr_gbp)::double                                                           as pause,
      (select ending_arr_gbp from m order by reporting_month_date desc limit 1)::double    as closing
    from m
  `);
  return rows[0] ?? null;
}

/** Active ARR by region at the latest month with SaaS data. */
export async function getArrByRegion(): Promise<RegionArr[]> {
  return runQuery<RegionArr>(`
    select
      coalesce(r.region_name, cc.region_hk)          as region,
      cc.active_arr_gbp::double                       as active_arr,
      cc.net_revenue_retention_rate::double           as nrr,
      cc.ending_active_customer_count::int            as customers
    from mart_executive_cfo_command_center as cc
    left join dim_region as r on cc.region_hk = r.region_hk
    where cc.reporting_scope = 'Region Total'
      and cc.reporting_month_date = (
        select max(reporting_month_date) from mart_executive_cfo_command_center
        where reporting_scope = 'Region Total' and active_arr_gbp > 0
      )
    order by cc.active_arr_gbp desc
  `);
}

// ---------------------------------------------------------------------------
// Revenue Recognition & deferred revenue (from the command center)
// ---------------------------------------------------------------------------

/** Revenue-recognition KPIs as at the latest actuals month (Company Total). */
export async function getRevenueKpis(): Promise<RevenueKpis | null> {
  const rows = await runQuery<RevenueKpis>(`
    select
      strftime(reporting_month_date, '%b %Y')        as month_label,
      reporting_month_date::varchar                  as month_iso,
      revenue_waterfall_billed_gbp::double           as billed,
      recognised_revenue_actual_gbp::double          as recognised_actual,
      recognition_variance_gbp::double               as recognition_variance,
      opening_deferred_revenue_gbp::double           as opening_deferred,
      new_billings_deferred_revenue_gbp::double      as new_billings_deferred,
      deferred_recognised_revenue_gbp::double        as recognised_deferred,
      closing_deferred_revenue_gbp::double           as closing_deferred,
      deferred_revenue_control_exception_count::int  as deferred_exceptions,
      unscheduled_billing_leakage_gbp::double        as unscheduled_leakage,
      revenue_governance_exception_count::int        as revenue_governance_exceptions,
      active_arr_gbp::double                          as active_arr,
      active_mrr_gbp::double                          as active_mrr
    from mart_executive_cfo_command_center
    where ${COMPANY_TOTAL} and recognised_revenue_actual_gbp > 0
    order by reporting_month_date desc
    limit 1
  `);
  return rows[0] ?? null;
}

/** Billed vs recognised + deferred balance by month (Company Total). */
export async function getRevRecTrend(): Promise<RevRecMonth[]> {
  return runQuery<RevRecMonth>(`
    select
      strftime(reporting_month_date, '%b %Y')                                       as month_label,
      reporting_month_date::varchar                                                 as month_iso,
      case when revenue_waterfall_billed_gbp > 0 then revenue_waterfall_billed_gbp end::double      as billed,
      case when recognised_revenue_actual_gbp > 0 then recognised_revenue_actual_gbp end::double    as recognised_actual,
      recognised_revenue_total_gbp::double                                          as recognised_total,
      closing_deferred_revenue_gbp::double                                          as closing_deferred
    from mart_executive_cfo_command_center
    where ${COMPANY_TOTAL}
      and reporting_month_date between date '2026-01-01' and date '2026-12-01'
    order by reporting_month_date
  `);
}

const SAAS_WINDOW = `reporting_month_date between date '2026-01-01' and date '2026-12-01'`;

/** Active ARR at product-family × segment grain, latest month (curated slice). */
export async function getArrByProductSegment(): Promise<ProductSegmentArr[]> {
  return runQuery<ProductSegmentArr>(`
    select
      product_family                       as product_family,
      customer_segment                     as customer_segment,
      sum(active_arr_gbp)::double           as active_arr
    from mart_saas_arr_by_product_segment
    where reporting_month_date = (
      select max(reporting_month_date) from mart_saas_arr_by_product_segment
      where ${SAAS_WINDOW} and active_arr_gbp > 0
    )
      and customer_segment in ('Enterprise', 'Mid-Market', 'SMB')
    group by 1, 2
  `);
}

/** FYTD ARR created vs lost by product family (curated slice). */
export async function getArrMovementByProduct(): Promise<ProductMovement[]> {
  return runQuery<ProductMovement>(`
    select
      product_family                                                          as product_family,
      sum(new_business_arr_gbp + expansion_arr_gbp + price_increase_arr_gbp)::double as gain,
      sum(contraction_arr_gbp + churn_arr_gbp + pause_arr_gbp)::double         as loss,
      sum(net_arr_delta_gbp)::double                                          as net
    from mart_saas_arr_by_product_segment
    where ${SAAS_WINDOW}
    group by 1
    order by sum(active_arr_gbp) desc
  `);
}

/** FYTD retention components by segment (rates computed in the app for correct weighting). */
export async function getRetentionBySegment(): Promise<SegmentRetention[]> {
  return runQuery<SegmentRetention>(`
    select
      customer_segment                     as customer_segment,
      sum(beginning_arr_gbp)::double        as beginning_arr,
      sum(gross_retained_arr_gbp)::double   as gross_retained,
      sum(net_retained_arr_gbp)::double     as net_retained,
      sum(beginning_customers)::int         as beginning_customers,
      sum(retained_customers)::int          as retained_customers,
      sum(churned_customers)::int           as churned_customers
    from mart_saas_retention_by_segment
    where ${SAAS_WINDOW}
      and customer_segment in ('Enterprise', 'Mid-Market', 'SMB')
    group by 1
    order by sum(beginning_arr_gbp) desc
  `);
}

/**
 * Company-wide SaaS trend for the SaaS Performance page. Filtered to months with
 * SaaS data so the latest row is the current snapshot (Jun 2026).
 */
export async function getExecutiveTrend(): Promise<ExecutiveMonth[]> {
  return runQuery<ExecutiveMonth>(`
    select
      reporting_month_date::varchar                                   as month_iso,
      strftime(reporting_month_date, '%b %Y')                         as month_label,
      active_arr_gbp::double                                          as active_arr_gbp,
      active_mrr_gbp::double                                          as active_mrr_gbp,
      net_revenue_retention_rate::double                             as nrr,
      gross_revenue_retention_rate::double                          as grr,
      churn_arr_gbp::double                                           as gross_churn_arr_gbp,
      case when beginning_arr_gbp > 0
           then churn_arr_gbp / beginning_arr_gbp end::double        as gross_churn_rate,
      new_business_arr_gbp::double                                    as new_business_arr_gbp,
      gross_expansion_arr_gbp::double                                 as gross_expansion_arr_gbp,
      ending_active_customer_count::integer                          as active_customers,
      has_any_executive_control_issue                                as has_any_control_issue
    from mart_executive_cfo_command_center
    where ${COMPANY_TOTAL}
      and active_arr_gbp > 0
    order by reporting_month_date
  `);
}

// ---------------------------------------------------------------------------
// Control Tower
// ---------------------------------------------------------------------------
// The warehouse deliberately retains control exceptions rather than hiding them.
// The command center already carries per-domain control flags + exception counts,
// so the trust view needs no extra data — aggregate them across the period.
export async function getControlSummary(): Promise<ControlSummary | null> {
  const rows = await runQuery<ControlSummary>(`
    select
      sum(financial_defect_row_count)::int                                          as financial_exceptions,
      bool_or(has_financial_performance_control_issue)                              as financial_flag,
      sum(defective_invoice_count + customer_months_with_over_applied_cash)::int    as o2c_exceptions,
      bool_or(has_o2c_control_issue)                                                as o2c_flag,
      sum(revenue_governance_exception_count)::int                                  as revenue_exceptions,
      bool_or(has_revenue_control_issue)                                            as revenue_flag,
      sum(deferred_revenue_control_exception_count)::int                            as deferred_exceptions,
      bool_or(has_deferred_revenue_control_issue)                                   as deferred_flag,
      sum(ap_control_exception_count)::int                                          as ap_exceptions,
      bool_or(has_ap_control_issue)                                                 as ap_flag,
      sum(workforce_control_issue_count)::int                                       as workforce_exceptions,
      bool_or(has_workforce_control_issue)                                          as workforce_flag,
      sum(saas_arr_control_issue_count + saas_retention_control_issue_count)::int   as saas_exceptions,
      bool_or(has_saas_control_issue)                                               as saas_flag,
      bool_or(has_any_executive_control_issue)                                      as any_flag,
      count(*)::int                                                                 as months
    from mart_executive_cfo_command_center
    where ${COMPANY_TOTAL}
  `);
  return rows[0] ?? null;
}

// ---------------------------------------------------------------------------
// Working Capital
// ---------------------------------------------------------------------------
// AR builds across the year as collections lag; AP is a point-in-time snapshot
// that only populates at the latest month. So this is a "current position as at
// the latest month" view. Company/region O2C + AP aggregates come from the
// command center; vendor-level AP detail comes from mart_ap_working_capital_control.

/** Company working-capital position as at the latest month with WC activity. */
export async function getWorkingCapitalPosition(): Promise<WorkingCapitalPosition | null> {
  const rows = await runQuery<WorkingCapitalPosition>(`
    select
      strftime(reporting_month_date, '%b %Y')        as month_label,
      reporting_month_date::varchar                  as month_iso,
      open_ar_exposure_gbp::double                   as open_ar,
      open_ap_liability_gbp::double                  as open_ap,
      net_ar_less_ap_exposure_gbp::double            as net_wc,
      overdue_ap_liability_gbp::double               as overdue_ap,
      cash_collected_gbp::double                     as cash_collected,
      operational_cash_pressure_gbp::double          as cash_pressure,
      cash_collection_rate::double                   as collection_rate,
      over_applied_cash_gbp::double                  as over_applied_cash,
      overdue_invoice_count::integer                 as overdue_invoice_count,
      duplicate_ap_exposure_gbp::double              as duplicate_ap_exposure
    from mart_executive_cfo_command_center
    where ${COMPANY_TOTAL}
      and (open_ar_exposure_gbp > 0 or open_ap_liability_gbp > 0)
    order by reporting_month_date desc
    limit 1
  `);
  return rows[0] ?? null;
}

/** AR exposure vs cash collected by month (Company Total). */
export async function getArCollectionsTrend(): Promise<ArCollectionsPoint[]> {
  return runQuery<ArCollectionsPoint>(`
    select
      strftime(reporting_month_date, '%b %Y')        as month_label,
      reporting_month_date::varchar                  as month_iso,
      open_ar_exposure_gbp::double                   as open_ar,
      cash_collected_gbp::double                     as cash_collected,
      billed_amount_gbp::double                      as billed
    from mart_executive_cfo_command_center
    where ${COMPANY_TOTAL}
      and (billed_amount_gbp > 0 or open_ar_exposure_gbp > 0)
    order by reporting_month_date
  `);
}

/** AP ageing buckets at the latest snapshot. */
export async function getApAgeing(): Promise<ApAgeing | null> {
  const rows = await runQuery<ApAgeing>(`
    select
      sum(current_open_amount_gbp)::double           as current_amt,
      sum(one_to_thirty_overdue_gbp)::double         as d1_30,
      sum(thirty_one_to_sixty_overdue_gbp)::double   as d31_60,
      sum(sixty_one_to_ninety_overdue_gbp)::double   as d61_90,
      sum(ninety_plus_overdue_gbp)::double           as d90_plus,
      sum(open_payable_liability_gbp)::double        as open_ap
    from mart_ap_working_capital_control
    where reporting_month_date = (select max(reporting_month_date) from mart_ap_working_capital_control)
  `);
  return rows[0] ?? null;
}

/** Top customers by open AR at the latest month (curated slice). */
export async function getTopArCustomers(limit = 12): Promise<ArCustomer[]> {
  return runQuery<ArCustomer>(`
    select
      customer_name                        as customer_name,
      customer_segment                     as customer_segment,
      region                               as region,
      open_ar::double                      as open_ar,
      overdue_invoices::int                as overdue_invoices
    from mart_o2c_top_customers
    order by open_ar desc
    limit ${Math.max(1, Math.floor(limit))}
  `);
}

/** AR collection components at region x segment grain (FYTD; app computes rates). */
export async function getArCollections(): Promise<ArCollection[]> {
  return runQuery<ArCollection>(`
    select
      region                               as region,
      customer_segment                     as customer_segment,
      sum(billed)::double                  as billed,
      sum(collected)::double               as collected
    from mart_o2c_by_region_segment
    group by 1, 2
  `);
}

/** Largest vendors by overdue AP at the latest snapshot. */
export async function getTopVendorsAp(limit = 10): Promise<VendorAp[]> {
  return runQuery<VendorAp>(`
    select
      vendor_name                                    as vendor_name,
      vendor_category                                as vendor_category,
      open_payable_liability_gbp::double             as open_ap,
      overdue_payable_liability_gbp::double          as overdue_ap,
      max_days_past_due::integer                     as max_dpd,
      has_critical_overdue_exposure                  as critical
    from mart_ap_working_capital_control
    where reporting_month_date = (select max(reporting_month_date) from mart_ap_working_capital_control)
      and open_payable_liability_gbp > 0
    order by overdue_payable_liability_gbp desc, open_payable_liability_gbp desc
    limit ${Math.max(1, Math.floor(limit))}
  `);
}

// ---------------------------------------------------------------------------
// Financial Performance (mart_financial_performance)
// ---------------------------------------------------------------------------
// The variance extract repeats actuals/budget across forecast versions, so we
// pin a single forecast version to deduplicate. There is one budget version.
const FC_BASE = `forecast_version_code = 'FC_BASE_CASE'`;

/** Company revenue/opex actual vs budget vs forecast for one month. */
export async function getFinancialSummary(
  monthIso: string,
): Promise<FinancialSummary | null> {
  assertMonthIso(monthIso);
  const rows = await runQuery<FinancialSummary>(`
    select
      sum(case when account_class = 'Revenue' then actual_amount_gbp else 0 end)::double   as revenue_actual,
      sum(case when account_class = 'Revenue' then budget_amount_gbp else 0 end)::double    as revenue_budget,
      sum(case when account_class = 'Revenue' then forecast_amount_gbp else 0 end)::double  as revenue_forecast,
      sum(case when account_class = 'Expense' then actual_amount_gbp else 0 end)::double    as opex_actual,
      sum(case when account_class = 'Expense' then budget_amount_gbp else 0 end)::double    as opex_budget,
      sum(case when account_class = 'Expense' then forecast_amount_gbp else 0 end)::double  as opex_forecast
    from mart_financial_performance
    where ${FC_BASE}
      and posting_period = date '${monthIso}'
  `);
  return rows[0] ?? null;
}

/** Operating-expense variance vs budget by department for one month. */
export async function getDepartmentVariance(
  monthIso: string,
): Promise<DepartmentVariance[]> {
  assertMonthIso(monthIso);
  return runQuery<DepartmentVariance>(`
    select
      coalesce(d.department_name, fp.department_id)        as department,
      sum(fp.actual_amount_gbp)::double                    as actual,
      sum(fp.budget_amount_gbp)::double                    as budget,
      sum(fp.actual_vs_budget_variance_gbp)::double        as variance
    from mart_financial_performance as fp
    left join dim_department as d on fp.department_hk = d.department_hk
    where fp.${FC_BASE}
      and fp.posting_period = date '${monthIso}'
      and fp.account_class = 'Expense'
    group by 1
    order by sum(fp.actual_amount_gbp) desc
  `);
}

/** Largest department × account variances vs budget for one month. */
export async function getTopAccountVariances(
  monthIso: string,
  limit = 12,
): Promise<AccountVariance[]> {
  assertMonthIso(monthIso);
  return runQuery<AccountVariance>(`
    select
      coalesce(d.department_name, fp.department_id)        as department,
      fp.account_name                                      as account,
      fp.account_class                                     as account_class,
      sum(fp.actual_amount_gbp)::double                    as actual,
      sum(fp.budget_amount_gbp)::double                    as budget,
      sum(fp.actual_vs_budget_variance_gbp)::double        as variance,
      max(fp.actual_vs_budget_favourability)               as favourability
    from mart_financial_performance as fp
    left join dim_department as d on fp.department_hk = d.department_hk
    where fp.${FC_BASE}
      and fp.posting_period = date '${monthIso}'
      and fp.actual_amount_gbp > 0
    group by 1, 2, 3
    order by abs(sum(fp.actual_vs_budget_variance_gbp)) desc
    limit ${Math.max(1, Math.floor(limit))}
  `);
}
