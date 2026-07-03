import { useState } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  LineChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from 'recharts';
import { useQuery } from '../hooks/useQuery';
import {
  getModelActualsFeed,
  getModelReadinessControls,
  getModelReadinessSummary,
  getOpeningBalanceSheet,
} from '../duckdb/queries';
import { TopBar } from '../components/TopBar';
import { KpiCard } from '../components/KpiCard';
import { ChartCard } from '../components/ChartCard';
import { StatusPill, type StatusTone } from '../components/StatusPill';
import { chart } from '../lib/theme';
import { formatCount, formatGbp, formatGbpCompact, formatPercent } from '../lib/format';
import type { ModelActualsMonth, ModelReadinessControl } from '../types';

const GRID = chart.grid;
const AXIS = chart.axis;

/** Published workbook identity — bump when a new model version is exported. */
const MODEL_WORKBOOK = {
  file: 'model/atlas_integrated_financial_model_v0.21.xlsx',
  name: 'Atlas Integrated Financial Model',
  version: 'v0.21',
  scenarios: 'Base / Downside / Upside',
};

/** Historical drivers the Excel model calibrates its assumptions against. */
const MODEL_DRIVERS = [
  { key: 'recognised_revenue', label: 'Revenue', kind: 'money' },
  { key: 'headline_arr', label: 'ARR', kind: 'money' },
  { key: 'nrr', label: 'NRR', kind: 'rate' },
  { key: 'cash_conversion', label: 'Cash conversion', kind: 'rate' },
  { key: 'opex', label: 'Opex', kind: 'money' },
  { key: 'active_fte', label: 'FTE', kind: 'count' },
] as const;
type DriverKey = (typeof MODEL_DRIVERS)[number]['key'];

const COVERAGE_DOMAINS = [
  { key: 'has_financial_actuals', label: 'Financial' },
  { key: 'has_revenue_actuals', label: 'Revenue' },
  { key: 'has_o2c_actuals', label: 'O2C' },
  { key: 'has_saas_actuals', label: 'SaaS' },
] as const;

function readinessTone(status: string): StatusTone {
  if (status === 'Ready') return 'favourable';
  if (status === 'Blocked') return 'adverse';
  if (status === 'Usable with review') return 'warning';
  return 'neutral';
}

function policyTone(control: ModelReadinessControl): StatusTone {
  if (control.model_blocking) return 'adverse';
  if (control.treatment === 'Usable with review') return 'warning';
  if (control.accepted_limitation) return 'neutral';
  return 'favourable';
}

function monthWindow(rows: ModelActualsMonth[]): ModelActualsMonth[] {
  const firstUsefulIndex = rows.findIndex(
    (row) =>
      row.recognised_revenue > 0 ||
      row.billings > 0 ||
      row.cash_collected > 0 ||
      row.closing_deferred_revenue > 0 ||
      row.use_in_excel_actuals,
  );
  const start = firstUsefulIndex < 0 ? 0 : Math.max(0, firstUsefulIndex - 2);
  const latestActualIndex = rows.reduce(
    (latest, row, index) => (row.use_in_excel_actuals ? index : latest),
    -1,
  );
  const end = latestActualIndex < 0 ? rows.length : Math.min(rows.length, latestActualIndex + 10);
  return rows.slice(start, end);
}

export function ForecastValuation() {
  const [driver, setDriver] = useState<DriverKey>('recognised_revenue');
  const summary = useQuery(getModelReadinessSummary, []);
  const feed = useQuery(getModelActualsFeed, []);
  const openingBalanceSheet = useQuery(getOpeningBalanceSheet, []);
  const controls = useQuery(getModelReadinessControls, []);

  const anyError = summary.error || feed.error || openingBalanceSheet.error || controls.error;
  if (anyError) {
    return (
      <div className="error-box">
        <strong>Could not load model-serving data.</strong>
        <div>{anyError.message}</div>
      </div>
    );
  }

  if (!summary.data || !feed.data || !openingBalanceSheet.data || !controls.data) {
    return (
      <div className="state">
        <div className="spinner" />
        <div>Loading CFO model-serving layer...</div>
      </div>
    );
  }

  const s = summary.data;
  const bs = openingBalanceSheet.data;
  const feedRows = feed.data;
  const chartRows = monthWindow(feedRows);
  const excelRows = feedRows.filter((row) => row.use_in_excel_actuals);
  const latestExcel = excelRows[excelRows.length - 1] ?? null;
  const blockedRows = feedRows.filter((row) => row.readiness_status === 'Blocked');
  const reviewRows = feedRows.filter((row) => row.readiness_status === 'Usable with review');
  const readinessTotal = Math.max(s.total_months, 1);
  const firstMonth = feedRows[0] ?? null;
  const lastMonth = feedRows[feedRows.length - 1] ?? null;

  return (
    <>
      <TopBar
        eyebrow="CFO Modelling Layer"
        title="Forecast & Valuation"
        subtitle="Can this data feed a real forecast and valuation model — and what happens next?"
        actions={
          <>
            <span className="scope-pill">Scope: Company Total</span>
            <span className="scope-pill">Scenario: ACTUALS</span>
          </>
        }
      />

      <div className="kpi-grid">
        <KpiCard
          label="Excel actual periods"
          value={formatCount(s.excel_actual_months)}
          sub={`${s.latest_excel_month_label ?? 'No month'} latest import-ready period`}
          status={{ tone: s.excel_actual_months > 0 ? 'favourable' : 'adverse', label: 'Model feed' }}
        />
        <KpiCard
          label="Latest model revenue"
          value={formatGbpCompact(s.latest_excel_revenue)}
          sub={`${formatGbpCompact(s.latest_excel_cash_collected)} cash collected`}
          status={{
            tone: latestExcel ? readinessTone(latestExcel.readiness_status) : 'adverse',
            label: latestExcel?.readiness_status ?? 'No actuals',
          }}
        />
        <KpiCard
          label="Opening cash"
          value={formatGbpCompact(s.opening_cash)}
          sub={`${s.opening_bs_date} statutory balance-sheet anchor`}
          status={{ tone: s.opening_bs_balanced ? 'favourable' : 'adverse', label: s.opening_bs_balanced ? 'Balanced' : 'Check' }}
        />
        <KpiCard
          label="Blocked periods"
          value={`${formatCount(s.blocked_months)} of ${formatCount(readinessTotal)}`}
          sub="excluded from the model baseline by policy"
          status={{ tone: s.blocked_months > 0 ? 'adverse' : 'favourable', label: s.blocked_months > 0 ? 'Excluded' : 'Clear' }}
        />
      </div>

      <div className="model-readiness-strip">
        <div className="readiness-part favourable" style={{ flexGrow: s.ready_months }}>
          <span>Ready</span>
          <strong>{formatCount(s.ready_months)}</strong>
        </div>
        <div className="readiness-part warning" style={{ flexGrow: s.review_months }}>
          <span>Review</span>
          <strong>{formatCount(s.review_months)}</strong>
        </div>
        <div className="readiness-part neutral" style={{ flexGrow: s.accepted_limitation_months }}>
          <span>Accepted</span>
          <strong>{formatCount(s.accepted_limitation_months)}</strong>
        </div>
        <div className="readiness-part adverse" style={{ flexGrow: s.blocked_months }}>
          <span>Blocked</span>
          <strong>{formatCount(s.blocked_months)}</strong>
        </div>
      </div>

      <div className="panel-grid model-panel-grid">
        <ChartCard
          className="hero"
          title="Actuals feed readiness"
          subtitle="Excel imports only periods marked by the warehouse contract"
          aside={`${formatCount(s.actual_months)} actual / ${formatCount(s.scheduled_months)} scheduled`}
        >
          <ResponsiveContainer width="100%" height={330}>
            <ComposedChart data={chartRows} margin={{ top: 8, right: 18, left: 6, bottom: 0 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="month_label" stroke={AXIS} fontSize={11} tickLine={false} minTickGap={18} />
              <YAxis yAxisId="money" stroke={AXIS} fontSize={11} tickLine={false} tickFormatter={(v: number) => formatGbpCompact(v)} />
              <YAxis yAxisId="status" orientation="right" hide domain={[0, 1]} />
              <Tooltip
                contentStyle={{ background: '#ffffff', border: '1px solid #d6d3cb', borderRadius: 8, color: '#1a1a1a' }}
                formatter={(value: number, name: string) => [
                  name === 'Excel-ready' ? (value > 0 ? 'Yes' : 'No') : formatGbp(value),
                  name,
                ]}
              />
              <ReferenceLine yAxisId="money" y={0} stroke="#d6d3cb" />
              <Bar yAxisId="status" dataKey={(row) => (row.use_in_excel_actuals ? 1 : 0)} name="Excel-ready" fill={chart.favourable} opacity={0.18} />
              <Line yAxisId="money" type="monotone" dataKey="recognised_revenue" name="Recognised revenue" stroke={chart.primary} strokeWidth={2.2} dot={false} />
              <Line yAxisId="money" type="monotone" dataKey="cash_collected" name="Cash collected" stroke={chart.favourable} strokeWidth={2} dot={false} />
              <Line yAxisId="money" type="monotone" dataKey="closing_deferred_revenue" name="Deferred revenue" stroke={chart.amber} strokeWidth={2} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </ChartCard>

        <div className="panel">
          <div className="panel-head">
            <div>
              <h3>Model handoff</h3>
              <p className="panel-sub">Historical basis for Excel v1.0</p>
            </div>
            <StatusPill tone={latestExcel ? readinessTone(latestExcel.readiness_status) : 'adverse'} label={latestExcel?.readiness_status ?? 'No actuals'} />
          </div>
          <ul className="kv">
            <li><span>Latest Excel period</span><strong>{latestExcel?.month_label ?? '-'}</strong></li>
            <li><span>Recognised revenue</span><strong>{formatGbp(latestExcel?.recognised_revenue)}</strong></li>
            <li><span>Billings</span><strong>{formatGbp(latestExcel?.billings)}</strong></li>
            <li><span>Cash collected</span><strong>{formatGbp(latestExcel?.cash_collected)}</strong></li>
            <li><span>ARR</span><strong>{formatGbp(latestExcel?.headline_arr)}</strong></li>
            <li><span>NRR</span><strong>{formatPercent(latestExcel?.nrr)}</strong></li>
          </ul>
          <p className="pnl-note">
            Excel should filter the feed to <code>use_in_excel_actuals_flag = true</code>.
          </p>
        </div>
      </div>

      {(() => {
        const spec = MODEL_DRIVERS.find((d) => d.key === driver)!;
        const driverRows = feedRows
          .filter((r) => r.period_status === 'Actual')
          .map((r) => ({
            month_label: r.month_label,
            value:
              driver === 'cash_conversion'
                ? r.billings > 0
                  ? r.cash_collected / r.billings
                  : null
                : (r[driver] as number | null),
          }))
          .filter((r) => r.value !== 0 || spec.kind === 'rate');
        const fmt = (v: number | null) =>
          v == null ? '-' : spec.kind === 'money' ? formatGbp(v) : spec.kind === 'rate' ? formatPercent(v) : formatCount(v);
        return (
          <ChartCard
            title="Historical model drivers"
            subtitle="Actual periods only — the calibration basis for the Excel forecast assumptions"
            aside={
              <div className="seg-toggle" role="group" aria-label="Model driver">
                {MODEL_DRIVERS.map((d) => (
                  <button
                    key={d.key}
                    type="button"
                    className={`seg-btn${driver === d.key ? ' active' : ''}`}
                    onClick={() => setDriver(d.key)}
                  >
                    {d.label}
                  </button>
                ))}
              </div>
            }
          >
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={driverRows} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
                <CartesianGrid stroke={GRID} vertical={false} />
                <XAxis dataKey="month_label" stroke={AXIS} fontSize={11} tickLine={false} minTickGap={24} />
                <YAxis
                  stroke={AXIS}
                  fontSize={11}
                  tickLine={false}
                  width={56}
                  domain={spec.kind === 'rate' ? ['auto', 'auto'] : [0, 'auto']}
                  tickFormatter={(v: number) =>
                    spec.kind === 'money' ? formatGbpCompact(v) : spec.kind === 'rate' ? formatPercent(v, 0) : formatCount(v)
                  }
                />
                <Tooltip
                  contentStyle={{ background: '#ffffff', border: '1px solid #d6d3cb', borderRadius: 8, color: '#1a1a1a' }}
                  formatter={(v: number) => [fmt(v), spec.label]}
                />
                <Line type="monotone" dataKey="value" stroke={chart.primary} strokeWidth={2.2} dot={false} connectNulls={false} />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>
        );
      })()}

      <div className="panel-grid model-panel-grid">
        <div className="panel">
          <div className="panel-head">
            <div>
              <h3>Domain coverage by model month</h3>
              <p className="panel-sub">Which governed domains back each month of the model-serving feed</p>
            </div>
            <span className="panel-aside">{formatCount(feedRows.length)} months</span>
          </div>
          <div className="coverage-grid">
            {COVERAGE_DOMAINS.map((domain) => (
              <div key={domain.key} className="coverage-row">
                <span className="coverage-label">{domain.label}</span>
                <div className="coverage-cells">
                  {feedRows.map((row) => (
                    <span
                      key={row.month_iso}
                      className={[
                        'coverage-cell',
                        row[domain.key] ? 'covered' : 'uncovered',
                        row.period_status === 'Scheduled' ? 'scheduled' : '',
                      ].join(' ')}
                      title={`${row.month_label} — ${domain.label}: ${row[domain.key] ? 'actuals present' : 'no actuals'}${row.period_status === 'Scheduled' ? ' (scheduled period)' : ''}`}
                    />
                  ))}
                </div>
              </div>
            ))}
            <div className="coverage-axis">
              <span>{firstMonth?.month_label ?? '-'}</span>
              <span>{s.latest_excel_month_label ? `Excel cut-off: ${s.latest_excel_month_label}` : ''}</span>
              <span>{lastMonth?.month_label ?? '-'}</span>
            </div>
          </div>
          <p className="pnl-note">
            Coverage flags come from the warehouse contract, not the dashboard: a month only
            feeds the Excel model when every core domain has validated actuals.
          </p>
        </div>

        <div className="panel">
          <div className="panel-head">
            <div>
              <h3>Model workspace</h3>
              <p className="panel-sub">Excel owns forecast assumptions and integrated statement logic</p>
            </div>
            <StatusPill tone="favourable" label={MODEL_WORKBOOK.version} />
          </div>
          <ul className="kv">
            <li><span>Workbook</span><strong>{MODEL_WORKBOOK.name}</strong></li>
            <li><span>Scenarios</span><strong>{MODEL_WORKBOOK.scenarios}</strong></li>
            <li><span>Actuals through</span><strong>{s.latest_excel_month_label ?? '-'}</strong></li>
          </ul>
          <div className="handoff-steps">
            <div className="handoff-step tone-favourable">
              <span className="handoff-name">Actuals feed</span>
              <span className="handoff-state">{formatCount(s.excel_actual_months)} import-ready months</span>
            </div>
            <div className={`handoff-step ${bs.is_balanced ? 'tone-favourable' : 'tone-adverse'}`}>
              <span className="handoff-name">Opening balance sheet</span>
              <span className="handoff-state">{bs.is_balanced ? 'Balanced anchor' : 'Balance check failed'}</span>
            </div>
            <div className="handoff-step tone-favourable">
              <span className="handoff-name">Readiness policy</span>
              <span className="handoff-state">{formatCount(controls.data.length)} controls classified</span>
            </div>
            <div className="handoff-step tone-pending">
              <span className="handoff-name">Outputs contract</span>
              <span className="handoff-state">Planned — scenario &amp; DCF outputs publish here</span>
            </div>
          </div>
          <a className="model-download" href={MODEL_WORKBOOK.file} download>
            Download Excel model ({MODEL_WORKBOOK.version})
          </a>
        </div>
      </div>

      <div className="panel-grid model-panel-grid">
        <div className="panel">
          <div className="panel-head">
            <div>
              <h3>Opening balance sheet</h3>
              <p className="panel-sub">Anchor point for the integrated three-statement model</p>
            </div>
            <StatusPill tone={bs.is_balanced ? 'favourable' : 'adverse'} label={bs.is_balanced ? 'Balanced' : 'Check'} />
          </div>
          <div className="table-scroll">
            <table className="pnl model-bs-table">
              <tbody>
                <tr><td className="row-label">Cash</td><td>{formatGbp(bs.cash)}</td></tr>
                <tr><td className="row-label">Accounts receivable</td><td>{formatGbp(bs.accounts_receivable)}</td></tr>
                <tr><td className="row-label">Prepaids and other current assets</td><td>{formatGbp(bs.prepaids_other_current_assets)}</td></tr>
                <tr><td className="row-label">Net PP&E</td><td>{formatGbp(bs.net_ppe)}</td></tr>
                <tr className="total"><td className="row-label">Total assets</td><td>{formatGbp(bs.total_assets)}</td></tr>
                <tr><td className="row-label">Accounts payable</td><td>{formatGbp(bs.accounts_payable)}</td></tr>
                <tr><td className="row-label">Deferred revenue</td><td>{formatGbp(bs.deferred_revenue)}</td></tr>
                <tr><td className="row-label">Debt</td><td>{formatGbp(bs.debt)}</td></tr>
                <tr><td className="row-label">Share capital</td><td>{formatGbp(bs.share_capital)}</td></tr>
                <tr><td className="row-label">Retained earnings</td><td>{formatGbp(bs.retained_earnings)}</td></tr>
                <tr className="total"><td className="row-label">Liabilities and equity</td><td>{formatGbp(bs.total_liabilities + bs.total_equity)}</td></tr>
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <div>
              <h3>Period exceptions</h3>
              <p className="panel-sub">Blocked periods and usable-with-review periods remain visible</p>
            </div>
          </div>
          <div className="focus-list">
            {blockedRows.slice(0, 3).map((row) => (
              <div key={row.month_iso} className="focus-row tone-adverse">
                <span className="focus-label">{row.month_label}</span>
                <span className="focus-detail">{formatCount(row.model_blocking_exceptions)} model-blocking exceptions</span>
                <span className="focus-go">Blocked</span>
              </div>
            ))}
            {reviewRows.slice(-3).map((row) => (
              <div key={row.month_iso} className="focus-row tone-warning">
                <span className="focus-label">{row.month_label}</span>
                <span className="focus-detail">{formatCount(row.review_exceptions)} review exceptions</span>
                <span className="focus-go">Review</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <ChartCard
        title="Model-readiness control policy"
        subtitle="Controls are classified before they reach Excel, Power BI, or commentary prompts"
      >
        <div className="table-scroll">
          <table className="pnl model-policy-table">
            <thead>
              <tr>
                <th className="row-label">Control</th>
                <th>Domain</th>
                <th>Severity</th>
                <th>Treatment</th>
                <th className="row-label">Model treatment</th>
              </tr>
            </thead>
            <tbody>
              {controls.data.map((control) => (
                <tr key={control.control_key}>
                  <td className="row-label">{control.control_name}</td>
                  <td>{control.control_domain}</td>
                  <td>{control.severity}</td>
                  <td><StatusPill tone={policyTone(control)} label={control.treatment} /></td>
                  <td className="row-label">{control.recommended_treatment}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </ChartCard>
    </>
  );
}
