import { useEffect, useMemo, useState } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { useQuery } from '../hooks/useQuery';
import {
  getReportingMonths,
  getCommandCenterKpis,
  getRevenueTrend,
} from '../duckdb/queries';
import { TopBar } from '../components/TopBar';
import { KpiCard } from '../components/KpiCard';
import { ChartCard } from '../components/ChartCard';
import { DataQualityBanner } from '../components/DataQualityBanner';
import { PnlSummary } from '../components/PnlSummary';
import type { StatusTone } from '../components/StatusPill';
import {
  formatGbp,
  formatGbpCompact,
  formatPercent,
  formatCount,
  formatSignedPercent,
} from '../lib/format';
import { chart } from '../lib/theme';

const ACCENT = chart.primary; // actual series — Atlas blue
const INFO = chart.secondary; // forecast series — cyan
const GRID = chart.grid;
const AXIS = chart.axis;

/** Favourability for "higher is better" metrics vs a plan figure. */
function varianceStatus(actual: number, plan: number): StatusTone {
  if (!plan) return 'neutral';
  const v = (actual - plan) / plan;
  if (v > 0.005) return 'favourable';
  if (v < -0.005) return 'adverse';
  return 'on-plan';
}

export function CfoCommandCenter() {
  const months = useQuery(getReportingMonths, []);
  const trend = useQuery(getRevenueTrend, []);
  const [selected, setSelected] = useState<string | null>(null);

  // Default to the latest CLOSED actuals month (financial actuals lag SaaS).
  useEffect(() => {
    if (selected || !months.data || months.data.length === 0) return;
    const withActuals = months.data.filter((m) => m.has_actuals);
    const latest =
      withActuals.length > 0
        ? withActuals[withActuals.length - 1]
        : months.data[months.data.length - 1];
    setSelected(latest.month_iso);
  }, [months.data, selected]);

  const kpis = useQuery(
    () => (selected ? getCommandCenterKpis(selected) : Promise.resolve(null)),
    [selected],
  );

  const monthOptions = months.data ?? [];
  const k = kpis.data;
  const hasActuals = !!k && k.actual_revenue > 0;

  const narrative = useMemo(() => {
    if (!k) return '';
    if (!hasActuals) {
      return (
        `${k.month_label} is a plan-only period — financial actuals have not yet been ` +
        `recognised. Budget revenue is ${formatGbp(k.budget_revenue)} and forecast is ` +
        `${formatGbp(k.forecast_revenue)}. SaaS run-rate ARR stands at ${formatGbp(k.active_arr)} ` +
        `on a governed Company-Total basis.`
      );
    }
    const revVar = (k.actual_revenue - k.budget_revenue) / k.budget_revenue;
    const dir = revVar >= 0 ? 'ahead of' : 'behind';
    return (
      `As at ${k.month_label}, actual revenue of ${formatGbp(k.actual_revenue)} is ` +
      `${formatSignedPercent(revVar)} ${dir} budget, delivering an operating result of ` +
      `${formatGbp(k.operating_result)} (${formatPercent(k.operating_margin)} margin). ` +
      `SaaS run-rate ARR is ${formatGbp(k.active_arr)} with ${formatPercent(k.nrr)} net revenue ` +
      `retention across ${formatCount(k.active_customers)} active customers. All figures are ` +
      `enforced to reporting_scope = 'Company Total' to prevent fan-out across region and ` +
      `business-unit rows.`
    );
  }, [k, hasActuals]);

  if (months.error || kpis.error || trend.error) {
    const msg = (months.error || kpis.error || trend.error)?.message;
    return <div className="error-box"><strong>Could not load data.</strong><div>{msg}</div></div>;
  }

  if (!k) {
    return (
      <div className="state">
        <div className="spinner" />
        <div>Loading executive mart into DuckDB-WASM…</div>
      </div>
    );
  }

  return (
    <>
      <TopBar
        title="CFO Command Center"
        subtitle="How is the business performing, are we on plan, where are the risks?"
        actions={
          <>
            <span className="scope-pill">Scope: Company Total</span>
            <select
              className="month-select"
              value={selected ?? ''}
              onChange={(e) => setSelected(e.target.value)}
              aria-label="Reporting month"
            >
              {monthOptions.map((m) => (
                <option key={m.month_iso} value={m.month_iso}>
                  {m.month_label}
                  {m.has_actuals ? '' : ' (plan)'}
                </option>
              ))}
            </select>
          </>
        }
      />

      <DataQualityBanner
        hasIssue={k.has_control_issue}
        domainsAffected={k.control_issue_domains}
        monthLabel={k.month_label}
      />

      {/* Row 1 — KPI spine. All values are reporting_scope = 'Company Total'. */}
      <div className="kpi-grid">
        <KpiCard
          label="Revenue (Actual)"
          value={hasActuals ? formatGbpCompact(k.actual_revenue) : '—'}
          sub={hasActuals ? `vs ${formatGbpCompact(k.budget_revenue)} budget` : `budget ${formatGbpCompact(k.budget_revenue)} · no actuals yet`}
          delta={
            hasActuals
              ? {
                  text: `${formatSignedPercent((k.actual_revenue - k.budget_revenue) / k.budget_revenue)} vs budget`,
                  direction: k.actual_revenue >= k.budget_revenue ? 'up' : 'down',
                }
              : undefined
          }
          status={hasActuals ? { tone: varianceStatus(k.actual_revenue, k.budget_revenue) } : { tone: 'neutral', label: 'Plan only' }}
        />
        <KpiCard
          label="Operating Result"
          value={hasActuals ? formatGbpCompact(k.operating_result) : '—'}
          sub={hasActuals ? `vs ${formatGbpCompact(k.budget_operating_result)} budget` : 'no actuals yet'}
          status={hasActuals ? { tone: varianceStatus(k.operating_result, k.budget_operating_result) } : { tone: 'neutral', label: 'Plan only' }}
        />
        <KpiCard
          label="Operating Margin"
          value={hasActuals ? formatPercent(k.operating_margin) : '—'}
          sub="operating basis (no COGS split)"
          status={hasActuals && k.operating_margin != null ? { tone: k.operating_margin >= 0 ? 'favourable' : 'adverse' } : { tone: 'neutral' }}
        />
        <KpiCard
          label="Active ARR"
          value={formatGbpCompact(k.active_arr)}
          sub={`run-rate · NRR ${formatPercent(k.nrr)}`}
          status={k.nrr != null ? { tone: k.nrr >= 1 ? 'favourable' : k.nrr >= 0.95 ? 'on-plan' : 'adverse' } : { tone: 'neutral' }}
        />
        <KpiCard
          label="Working Capital Exposure"
          value={formatGbpCompact(k.net_working_capital)}
          sub={`AR ${formatGbpCompact(k.open_ar)} less AP ${formatGbpCompact(k.open_ap)}`}
          status={{ tone: 'neutral', label: 'Monitor' }}
        />
      </div>

      {/* P&L summary (operating basis) */}
      <PnlSummary kpis={k} />

      {/* Row 2 — performance diagnosis */}
      <div className="panel-grid">
        <ChartCard
          title="Actual vs Budget vs Forecast"
          subtitle="Company-total revenue by month (GBP) · actuals stop at the last closed month"
        >
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={trend.data ?? []} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="month_label" stroke={AXIS} fontSize={12} tickLine={false} />
              <YAxis
                stroke={AXIS}
                fontSize={12}
                tickLine={false}
                width={56}
                tickFormatter={(v: number) => formatGbpCompact(v)}
              />
              <Tooltip
                contentStyle={{ background: '#16213a', border: '1px solid #243150', borderRadius: 10, color: '#e8eef9' }}
                formatter={(v: number, name) => {
                  const labels: Record<string, string> = {
                    actual_revenue: 'Actual',
                    budget_revenue: 'Budget',
                    forecast_revenue: 'Forecast',
                  };
                  return [formatGbp(v), labels[name as string] ?? name];
                }}
              />
              <Legend
                formatter={(v) =>
                  ({ actual_revenue: 'Actual', budget_revenue: 'Budget', forecast_revenue: 'Forecast' }[
                    v as string
                  ] ?? v)
                }
              />
              <Line type="monotone" dataKey="actual_revenue" stroke={ACCENT} strokeWidth={2.5} dot={false} connectNulls={false} />
              <Line type="monotone" dataKey="budget_revenue" stroke={AXIS} strokeWidth={1.5} strokeDasharray="5 4" dot={false} />
              <Line type="monotone" dataKey="forecast_revenue" stroke={INFO} strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Variance by driver"
          subtitle="Planned for the Financial Performance page"
        >
          <div className="placeholder-chart">
            <p>Driver-level variance is not exposed on the executive mart.</p>
            <p className="src">Will be powered by <code>mart_financial_performance</code> (department × account variance).</p>
          </div>
        </ChartCard>
      </div>

      {/* Row 3 — domain health strip */}
      <div className="tile-grid">
        <DomainTile
          title="SaaS Health"
          primary={formatPercent(k.nrr)}
          primaryLabel="Net revenue retention"
          secondary={`${formatCount(k.active_customers)} active customers`}
          source="mart_saas_arr_movement · retention"
          tone={k.nrr != null && k.nrr >= 1 ? 'favourable' : 'on-plan'}
        />
        <DomainTile
          title="Working Capital"
          primary={formatGbpCompact(k.net_working_capital)}
          primaryLabel="Net AR less AP"
          secondary={`AR ${formatGbpCompact(k.open_ar)} · AP ${formatGbpCompact(k.open_ap)}`}
          source="mart_o2c · mart_ap_working_capital_control"
          tone="neutral"
        />
        <DomainTile
          title="Workforce Cost"
          primary={formatGbpCompact(k.payroll_cost)}
          primaryLabel="Monthly payroll"
          secondary={`${formatCount(k.headcount)} active headcount`}
          source="mart_workforce_cost_control"
          tone="neutral"
        />
        <DomainTile
          title="Controls"
          primary={k.has_control_issue ? `${k.control_issue_domains} flagged` : 'Clean'}
          primaryLabel="Control exceptions"
          secondary={k.has_control_issue ? 'Review Control Tower' : 'No exceptions this month'}
          source="control marts"
          tone={k.has_control_issue ? 'adverse' : 'favourable'}
        />
      </div>

      {/* Executive narrative */}
      <div className="narrative">
        <h3>Executive Summary</h3>
        <p>{narrative}</p>
      </div>
    </>
  );
}

interface DomainTileProps {
  title: string;
  primary: string;
  primaryLabel: string;
  secondary: string;
  source: string;
  tone: StatusTone;
}

function DomainTile({ title, primary, primaryLabel, secondary, source, tone }: DomainTileProps) {
  return (
    <div className={`tile tone-${tone}`}>
      <div className="tile-title">{title}</div>
      <div className="tile-primary">{primary}</div>
      <div className="tile-primary-label">{primaryLabel}</div>
      <div className="tile-secondary">{secondary}</div>
      <div className="tile-source">{source}</div>
    </div>
  );
}
