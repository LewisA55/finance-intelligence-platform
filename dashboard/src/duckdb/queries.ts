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
