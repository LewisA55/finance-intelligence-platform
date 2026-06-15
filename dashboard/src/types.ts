/** One Company-Total reporting month (used by the month selector). */
export interface ReportingMonth {
  month_iso: string; // 'YYYY-MM-DD' (month start)
  month_label: string; // 'Jun 2026'
  has_actuals: boolean; // financial actuals exist (actual_revenue > 0)
  has_saas: boolean; // SaaS run-rate exists (active_arr > 0)
}

/** Company-Total KPI snapshot for a single reporting month. */
export interface CommandCenterKpis {
  month_iso: string;
  month_label: string;
  actual_revenue: number;
  budget_revenue: number;
  forecast_revenue: number;
  actual_expense: number;
  budget_expense: number;
  forecast_expense: number;
  operating_result: number;
  budget_operating_result: number;
  forecast_operating_result: number;
  operating_margin: number | null;
  active_arr: number;
  active_mrr: number;
  nrr: number | null;
  open_ar: number;
  open_ap: number;
  net_working_capital: number;
  cash_pressure: number;
  payroll_cost: number;
  headcount: number;
  active_customers: number;
  has_control_issue: boolean;
  control_issue_domains: number;
}

/** Actual vs budget vs forecast revenue, one row per month. */
export interface RevenueTrendPoint {
  month_label: string;
  month_iso: string;
  actual_revenue: number | null; // null after the last closed actuals month
  budget_revenue: number;
  forecast_revenue: number;
}

/** Validation / audit facts for the debug panel. */
export interface ValidationInfo {
  tables: string[];
  execMartRowCount: number;
  scopeCounts: { reporting_scope: string; rows: number }[];
  latestReportingMonth: string;
  latestActualsMonth: string | null;
  companyTotalRowCount: number;
}

/** Financial Performance — company revenue/opex actual vs budget vs forecast for a month. */
export interface FinancialSummary {
  revenue_actual: number;
  revenue_budget: number;
  revenue_forecast: number;
  opex_actual: number;
  opex_budget: number;
  opex_forecast: number;
}

/** Operating-expense variance by department for a month. */
export interface DepartmentVariance {
  department: string;
  actual: number;
  budget: number;
  variance: number; // actual - budget (negative = under budget = favourable for opex)
}

/** Largest department × account variances for a month. */
export interface AccountVariance {
  department: string;
  account: string;
  account_class: string;
  actual: number;
  budget: number;
  variance: number;
  favourability: string | null; // 'Favourable' | 'Adverse'
}

/** Working Capital — company position as at the latest month (from command center). */
export interface WorkingCapitalPosition {
  month_label: string;
  month_iso: string;
  open_ar: number;
  open_ap: number;
  net_wc: number;
  overdue_ap: number;
  cash_collected: number;
  cash_pressure: number;
  collection_rate: number | null;
  over_applied_cash: number;
  overdue_invoice_count: number;
  duplicate_ap_exposure: number;
}

/** AR exposure vs cash collected, one row per month. */
export interface ArCollectionsPoint {
  month_label: string;
  month_iso: string;
  open_ar: number;
  cash_collected: number;
  billed: number;
}

/** AP ageing buckets at the latest snapshot. */
export interface ApAgeing {
  current_amt: number;
  d1_30: number;
  d31_60: number;
  d61_90: number;
  d90_plus: number;
  open_ap: number;
}

/** Vendor-level AP at the latest snapshot. */
export interface VendorAp {
  vendor_name: string;
  vendor_category: string;
  open_ap: number;
  overdue_ap: number;
  max_dpd: number;
  critical: boolean;
}

/** Control Tower — aggregated control exceptions by domain across the period. */
export interface ControlSummary {
  financial_exceptions: number;
  financial_flag: boolean;
  o2c_exceptions: number;
  o2c_flag: boolean;
  revenue_exceptions: number;
  revenue_flag: boolean;
  deferred_exceptions: number;
  deferred_flag: boolean;
  ap_exceptions: number;
  ap_flag: boolean;
  workforce_exceptions: number;
  workforce_flag: boolean;
  saas_exceptions: number;
  saas_flag: boolean;
  any_flag: boolean;
  months: number;
}

/** SaaS KPI snapshot for the latest month (Company Total). */
export interface SaasKpis {
  month_label: string;
  month_iso: string;
  active_arr: number;
  active_mrr: number;
  nrr: number | null;
  grr: number | null;
  logo_retention: number | null;
  logo_churn: number | null;
  net_arr_delta: number;
  new_customers: number;
  churned_customers: number;
  paused_customers: number;
  retained_customers: number;
  beginning_customers: number;
  ending_customers: number;
  subscriptions: number;
  active_subscriptions: number;
}

/** Period ARR walk (opening → movements → closing). */
export interface ArrWalk {
  opening: number;
  new_business: number;
  expansion: number;
  price_increase: number;
  contraction: number;
  churn: number;
  pause: number;
  closing: number;
}

/** ARR by region at the latest month. */
export interface RegionArr {
  region: string;
  active_arr: number;
  nrr: number | null;
  customers: number;
}

/** Active ARR at product-family × segment grain (latest month). */
export interface ProductSegmentArr {
  product_family: string;
  customer_segment: string;
  active_arr: number;
}

/** FYTD ARR created vs lost by product family. */
export interface ProductMovement {
  product_family: string;
  gain: number; // new + expansion + price increase
  loss: number; // contraction + churn + pause
  net: number;
}

/** FYTD retention components by segment (rates computed in the app). */
export interface SegmentRetention {
  customer_segment: string;
  beginning_arr: number;
  gross_retained: number;
  net_retained: number;
  beginning_customers: number;
  retained_customers: number;
  churned_customers: number;
}

/** Revenue Recognition KPI snapshot (latest actuals month, Company Total). */
export interface RevenueKpis {
  month_label: string;
  month_iso: string;
  billed: number;
  recognised_actual: number;
  recognition_variance: number;
  opening_deferred: number;
  new_billings_deferred: number;
  recognised_deferred: number;
  closing_deferred: number;
  deferred_exceptions: number;
  unscheduled_leakage: number;
  revenue_governance_exceptions: number;
  active_arr: number;
  active_mrr: number;
}

/** Billed vs recognised + deferred balance, one row per month. */
export interface RevRecMonth {
  month_label: string;
  month_iso: string;
  billed: number | null; // null after last billed month
  recognised_actual: number | null; // null after last actuals month
  recognised_total: number; // incl. scheduled future recognition
  closing_deferred: number;
}

/** Company-wide SaaS trend (SaaS Performance page). */
export interface ExecutiveMonth {
  month_iso: string;
  month_label: string;
  active_arr_gbp: number;
  active_mrr_gbp: number;
  nrr: number | null;
  grr: number | null;
  gross_churn_arr_gbp: number;
  gross_churn_rate: number | null;
  new_business_arr_gbp: number;
  gross_expansion_arr_gbp: number;
  active_customers: number;
  has_any_control_issue: boolean;
}
