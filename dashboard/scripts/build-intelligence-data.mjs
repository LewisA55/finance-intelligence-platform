import { createReadStream } from 'node:fs';
import { mkdir, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import readline from 'node:readline';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, '..', '..');
const csvDir = join(repoRoot, 'data', 'exports', 'powerbi', 'csv');
const targetDir = join(here, '..', 'public', 'data');

const productFamily = (productId) => {
  if (['100', '101', '102'].includes(productId)) return 'Core';
  if (['103', '104', '105'].includes(productId)) return 'Analytics';
  if (['106', '107', '108'].includes(productId)) return 'AI';
  if (['109', '110', '111'].includes(productId)) return 'Professional Services';
  if (productId === '112') return 'Legacy';
  return 'Other';
};

const toNum = (value) => {
  if (value == null || value === '') return 0;
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
};

const toBool = (value) => String(value).toLowerCase() === 'true';

function parseCsvLine(line) {
  const out = [];
  let cur = '';
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (ch === '"') {
      if (quoted && line[i + 1] === '"') {
        cur += '"';
        i += 1;
      } else {
        quoted = !quoted;
      }
    } else if (ch === ',' && !quoted) {
      out.push(cur);
      cur = '';
    } else {
      cur += ch;
    }
  }
  out.push(cur);
  return out;
}

async function scanCsv(name, onRow) {
  const input = createReadStream(join(csvDir, `${name}.csv`));
  const rl = readline.createInterface({ input, crlfDelay: Infinity });
  let header = null;
  let index = null;
  for await (const line of rl) {
    if (header == null) {
      header = parseCsvLine(line);
      index = new Map(header.map((col, i) => [col, i]));
      continue;
    }
    if (!line) continue;
    const parts = parseCsvLine(line);
    const row = (col) => parts[index.get(col)] ?? '';
    onRow(row);
  }
}

async function readMap(name, keyCol, valueCols) {
  const map = new Map();
  await scanCsv(name, (row) => {
    const value = {};
    for (const col of valueCols) value[col] = row(col);
    map.set(row(keyCol), value);
  });
  return map;
}

function add(map, key, dims, values) {
  let row = map.get(key);
  if (!row) {
    row = { ...dims };
    for (const [name, value] of Object.entries(values)) row[name] = value;
    map.set(key, row);
    return row;
  }
  for (const [name, value] of Object.entries(values)) row[name] += value;
  return row;
}

function rows(map) {
  return Array.from(map.values());
}

function csvEscape(value) {
  if (value == null) return '';
  const s = String(value);
  return /[",\n\r]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s;
}

async function writeCsv(name, columns, data) {
  const lines = [
    columns.join(','),
    ...data.map((row) => columns.map((col) => csvEscape(row[col])).join(',')),
  ];
  await writeFile(join(targetDir, `${name}.csv`), `${lines.join('\n')}\n`, 'utf8');
  console.log(`wrote ${name}.csv (${data.length.toLocaleString()} rows)`);
}

await mkdir(targetDir, { recursive: true });

const regions = await readMap('dim_region', 'region_hk', ['region_name']);
const customers = await readMap('dim_customer', 'customer_hk', ['customer_segment']);
const departments = await readMap('dim_department', 'department_hk', ['department_name']);

const saasMonthly = new Map();
const saasProduct = new Map();
await scanCsv('mart_saas_arr_movement', (r) => {
  const month = r('reporting_month_date');
  const family = productFamily(r('product_id'));
  const segment = r('customer_segment') || 'Unknown';
  const values = {
    subscription_count: toNum(r('subscription_count')),
    active_subscription_count: toNum(r('active_subscription_count')),
    beginning_arr_gbp: toNum(r('beginning_arr_gbp')),
    new_business_arr_gbp: toNum(r('new_business_arr_gbp')),
    expansion_arr_gbp: toNum(r('expansion_arr_gbp')),
    price_increase_arr_gbp: toNum(r('price_increase_arr_gbp')),
    contraction_arr_gbp: toNum(r('contraction_arr_gbp')),
    churn_arr_gbp: toNum(r('churn_arr_gbp')),
    pause_arr_gbp: toNum(r('pause_arr_gbp')),
    net_arr_delta_gbp: toNum(r('net_arr_delta_gbp')),
    ending_arr_gbp: toNum(r('ending_arr_gbp')),
    active_arr_gbp: toNum(r('active_arr_gbp')),
    active_mrr_gbp: toNum(r('active_mrr_gbp')),
    control_exception_count: toBool(r('has_saas_control_issue')) ? 1 : 0,
  };
  add(saasMonthly, month, { month_iso: month }, values);
  add(saasProduct, `${month}|${family}|${segment}`, {
    month_iso: month,
    product_family: family,
    customer_segment: segment,
  }, values);
});

const saasSegment = new Map();
await scanCsv('mart_saas_retention', (r) => {
  const month = r('reporting_month_date');
  const segment = r('customer_segment') || 'Unknown';
  add(saasSegment, `${month}|${segment}`, {
    month_iso: month,
    customer_segment: segment,
  }, {
    beginning_arr_gbp: toNum(r('beginning_arr_gbp')),
    gross_retained_arr_gbp: toNum(r('gross_retained_arr_gbp')),
    net_retained_arr_gbp: toNum(r('net_retained_arr_gbp')),
    new_business_arr_gbp: toNum(r('new_business_arr_gbp')),
    expansion_arr_gbp: toNum(r('expansion_arr_gbp')),
    contraction_arr_gbp: toNum(r('contraction_arr_gbp')),
    churn_arr_gbp: toNum(r('churn_arr_gbp')),
    pause_arr_gbp: toNum(r('pause_arr_gbp')),
    beginning_customers: toNum(r('beginning_active_customer_count')),
    ending_customers: toNum(r('ending_active_customer_count')),
    retained_customers: toNum(r('retained_customer_count')),
    churned_customers: toNum(r('churned_customer_count')),
    paused_customers: toNum(r('paused_customer_count')),
    new_customers: toNum(r('new_customer_count')),
    control_exception_count: toBool(r('has_saas_retention_control_issue')) ? 1 : 0,
  });
});

const revenueQuality = new Map();
await scanCsv('mart_revenue_waterfall', (r) => {
  const month = r('reporting_month').slice(0, 10);
  add(revenueQuality, month, { month_iso: month }, {
    billed_amount_gbp: toNum(r('billed_amount_gbp')),
    recognised_revenue_actual_gbp: toNum(r('recognised_revenue_actual_gbp')),
    recognised_revenue_scheduled_gbp: toNum(r('recognised_revenue_scheduled_gbp')),
    recognised_revenue_total_gbp: toNum(r('recognised_revenue_total_gbp')),
    unscheduled_billing_leakage_gbp: toNum(r('unscheduled_billing_leakage_gbp')),
    recognition_variance_gbp: toNum(r('recognition_variance_gbp')),
    billed_invoice_count: toNum(r('billed_invoice_count')),
    billed_invoice_line_count: toNum(r('billed_invoice_line_count')),
    actual_recognition_row_count: toNum(r('actual_recognition_row_count')),
    scheduled_recognition_row_count: toNum(r('scheduled_recognition_row_count')),
    billing_only_count: toBool(r('is_billing_only')) ? 1 : 0,
    recognition_only_count: toBool(r('is_recognition_only')) ? 1 : 0,
    matched_count: toBool(r('is_billing_and_recognition')) ? 1 : 0,
    scheduled_backlog_count: toBool(r('is_scheduled_backlog_month')) ? 1 : 0,
    governance_exception_count: toBool(r('has_revenue_governance_exception')) ? 1 : 0,
  });
});

const deferredTrend = new Map();
await scanCsv('mart_deferred_revenue_control', (r) => {
  const month = r('period_month');
  const status = r('period_status');
  const category = r('revenue_category');
  add(deferredTrend, `${month}|${status}|${category}`, {
    month_iso: month,
    period_status: status,
    revenue_category: category,
  }, {
    opening_deferred_gbp: toNum(r('corporate_opening_deferred_revenue_gbp')),
    new_billings_deferred_gbp: toNum(r('corporate_new_billings_deferred_gbp')),
    recognised_revenue_gbp: toNum(r('corporate_recognised_revenue_gbp')),
    closing_deferred_gbp: toNum(r('corporate_closing_deferred_revenue_gbp')),
    rollforward_exception_count: toNum(r('corporate_rollforward_exception_count')),
    continuity_exception_count: toNum(r('corporate_continuity_exception_count')),
    defect_row_count: toNum(r('corporate_defect_row_count')),
    control_exception_count: toBool(r('has_deferred_revenue_control_exception')) ? 1 : 0,
  });
});

const cashConversion = new Map();
await scanCsv('mart_o2c_customer_collections', (r) => {
  const month = r('invoice_month');
  const region = regions.get(r('region_hk'))?.region_name || 'Unassigned';
  const segment = customers.get(r('customer_hk'))?.customer_segment || 'Unknown';
  add(cashConversion, `${month}|${region}|${segment}`, {
    month_iso: month,
    region,
    customer_segment: segment,
  }, {
    billed_amount_gbp: toNum(r('billed_amount_gbp')),
    allocated_amount_gbp: toNum(r('allocated_amount_gbp')),
    open_invoice_exposure_gbp: toNum(r('open_invoice_exposure_gbp')),
    over_applied_cash_gbp: toNum(r('over_applied_allocation_amount_gbp')),
    invoice_count: toNum(r('invoice_count')),
    overdue_invoice_count: toNum(r('overdue_invoice_status_count')),
    disputed_invoice_count: toNum(r('disputed_invoice_status_count')),
    defective_invoice_count: toNum(r('defective_invoice_count')),
    over_allocated_invoice_count: toNum(r('invoices_over_allocated')),
    customer_months: 1,
  });
});

const workforce = new Map();
await scanCsv('mart_workforce_cost_control', (r) => {
  const month = r('reporting_month_date');
  const department = departments.get(r('department_hk'))?.department_name || r('department_id') || 'Unknown';
  add(workforce, `${month}|${department}`, {
    month_iso: month,
    department,
  }, {
    payroll_cost_gbp: toNum(r('payroll_cost_gbp')),
    base_salary_cost_gbp: toNum(r('base_salary_cost_gbp')),
    employer_tax_cost_gbp: toNum(r('employer_tax_cost_gbp')),
    benefits_cost_gbp: toNum(r('benefits_cost_gbp')),
    bonus_accrual_cost_gbp: toNum(r('bonus_accrual_cost_gbp')),
    active_headcount_count: toNum(r('active_headcount_count')),
    active_fte_count: toNum(r('active_fte_count')),
    ghost_headcount_count: toNum(r('ghost_headcount_count')),
    status_active_mismatch_count: toNum(r('status_active_mismatch_count')),
    open_position_count: toNum(r('open_position_count')),
    open_position_monthly_salary_exposure_gbp: toNum(r('open_position_monthly_salary_exposure_gbp')),
    monthly_salary_exposure_gbp: toNum(r('monthly_salary_exposure_gbp')),
    control_exception_count: toBool(r('has_workforce_control_issue')) ? 1 : 0,
  });
});

const controls = new Map();
function addControl(month, domain, exceptions, observations = 1) {
  add(controls, `${month}|${domain}`, { month_iso: month, domain }, {
    exception_count: exceptions,
    flagged_observation_count: exceptions > 0 ? observations : 0,
  });
}

for (const r of rows(saasMonthly)) addControl(r.month_iso, 'SaaS ARR', r.control_exception_count);
for (const r of rows(saasSegment)) addControl(r.month_iso, 'SaaS Retention', r.control_exception_count);
for (const r of rows(revenueQuality)) addControl(r.month_iso, 'Revenue Recognition', r.governance_exception_count);
for (const r of rows(deferredTrend)) addControl(r.month_iso, 'Deferred Revenue', r.control_exception_count);
for (const r of rows(cashConversion)) {
  addControl(r.month_iso, 'Order-to-Cash', r.defective_invoice_count + r.over_allocated_invoice_count);
}
for (const r of rows(workforce)) addControl(r.month_iso, 'Workforce', r.control_exception_count);

const apMonthly = new Map();
await scanCsv('mart_ap_working_capital_control', (r) => {
  const month = r('reporting_month_date');
  add(apMonthly, month, { month_iso: month }, {
    control_exception_count: toBool(r('has_ap_control_exception')) ? 1 : 0,
    duplicate_exposure_gbp: toNum(r('active_duplicate_exposure_gbp')),
    cutoff_failure_exposure_gbp: toNum(r('active_ap_cutoff_failure_exposure_gbp')),
  });
});
for (const r of rows(apMonthly)) {
  addControl(r.month_iso, 'Accounts Payable', r.control_exception_count);
}

const financialMonthly = new Map();
await scanCsv('mart_financial_performance', (r) => {
  const month = r('posting_period');
  add(financialMonthly, month, { month_iso: month }, {
    defect_count: toBool(r('is_defect')) ? 1 : 0,
  });
});
for (const r of rows(financialMonthly)) addControl(r.month_iso, 'Financial Performance', r.defect_count);

await writeCsv('dashboard_saas_monthly_intelligence', [
  'month_iso', 'subscription_count', 'active_subscription_count', 'beginning_arr_gbp',
  'new_business_arr_gbp', 'expansion_arr_gbp', 'price_increase_arr_gbp',
  'contraction_arr_gbp', 'churn_arr_gbp', 'pause_arr_gbp', 'net_arr_delta_gbp',
  'ending_arr_gbp', 'active_arr_gbp', 'active_mrr_gbp', 'control_exception_count',
], rows(saasMonthly).sort((a, b) => a.month_iso.localeCompare(b.month_iso)));

await writeCsv('dashboard_saas_segment_trend', [
  'month_iso', 'customer_segment', 'beginning_arr_gbp', 'gross_retained_arr_gbp',
  'net_retained_arr_gbp', 'new_business_arr_gbp', 'expansion_arr_gbp',
  'contraction_arr_gbp', 'churn_arr_gbp', 'pause_arr_gbp', 'beginning_customers',
  'ending_customers', 'retained_customers', 'churned_customers', 'paused_customers',
  'new_customers', 'control_exception_count',
], rows(saasSegment).sort((a, b) => `${a.month_iso}|${a.customer_segment}`.localeCompare(`${b.month_iso}|${b.customer_segment}`)));

await writeCsv('dashboard_saas_product_trend', [
  'month_iso', 'product_family', 'customer_segment', 'subscription_count',
  'active_subscription_count', 'beginning_arr_gbp', 'new_business_arr_gbp',
  'expansion_arr_gbp', 'price_increase_arr_gbp', 'contraction_arr_gbp',
  'churn_arr_gbp', 'pause_arr_gbp', 'net_arr_delta_gbp', 'ending_arr_gbp',
  'active_arr_gbp', 'active_mrr_gbp', 'control_exception_count',
], rows(saasProduct).sort((a, b) => `${a.month_iso}|${a.product_family}|${a.customer_segment}`.localeCompare(`${b.month_iso}|${b.product_family}|${b.customer_segment}`)));

await writeCsv('dashboard_revenue_quality', [
  'month_iso', 'billed_amount_gbp', 'recognised_revenue_actual_gbp',
  'recognised_revenue_scheduled_gbp', 'recognised_revenue_total_gbp',
  'unscheduled_billing_leakage_gbp', 'recognition_variance_gbp',
  'billed_invoice_count', 'billed_invoice_line_count', 'actual_recognition_row_count',
  'scheduled_recognition_row_count', 'billing_only_count', 'recognition_only_count',
  'matched_count', 'scheduled_backlog_count', 'governance_exception_count',
], rows(revenueQuality).sort((a, b) => a.month_iso.localeCompare(b.month_iso)));

await writeCsv('dashboard_deferred_revenue_trend', [
  'month_iso', 'period_status', 'revenue_category', 'opening_deferred_gbp',
  'new_billings_deferred_gbp', 'recognised_revenue_gbp', 'closing_deferred_gbp',
  'rollforward_exception_count', 'continuity_exception_count', 'defect_row_count',
  'control_exception_count',
], rows(deferredTrend).sort((a, b) => `${a.month_iso}|${a.period_status}|${a.revenue_category}`.localeCompare(`${b.month_iso}|${b.period_status}|${b.revenue_category}`)));

await writeCsv('dashboard_cash_conversion', [
  'month_iso', 'region', 'customer_segment', 'billed_amount_gbp',
  'allocated_amount_gbp', 'open_invoice_exposure_gbp', 'over_applied_cash_gbp',
  'invoice_count', 'overdue_invoice_count', 'disputed_invoice_count',
  'defective_invoice_count', 'over_allocated_invoice_count', 'customer_months',
], rows(cashConversion).sort((a, b) => `${a.month_iso}|${a.region}|${a.customer_segment}`.localeCompare(`${b.month_iso}|${b.region}|${b.customer_segment}`)));

await writeCsv('dashboard_workforce_capacity', [
  'month_iso', 'department', 'payroll_cost_gbp', 'base_salary_cost_gbp',
  'employer_tax_cost_gbp', 'benefits_cost_gbp', 'bonus_accrual_cost_gbp',
  'active_headcount_count', 'active_fte_count', 'ghost_headcount_count',
  'status_active_mismatch_count', 'open_position_count',
  'open_position_monthly_salary_exposure_gbp', 'monthly_salary_exposure_gbp',
  'control_exception_count',
], rows(workforce).sort((a, b) => `${a.month_iso}|${a.department}`.localeCompare(`${b.month_iso}|${b.department}`)));

await writeCsv('dashboard_control_history', [
  'month_iso', 'domain', 'exception_count', 'flagged_observation_count',
], rows(controls).sort((a, b) => `${a.month_iso}|${a.domain}`.localeCompare(`${b.month_iso}|${b.domain}`)));
