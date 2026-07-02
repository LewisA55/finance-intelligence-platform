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
  ReferenceLine,
} from 'recharts';
import { useQuery } from '../hooks/useQuery';
import {
  getReportingMonths,
  getCommandCenterKpis,
  getRevenueTrend,
  getModelReadinessSummary,
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
import { NAV, type PageId } from '../nav';
import type { CommandCenterKpis, ModelReadinessSummary } from '../types';

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

const pageLabel = (id: PageId) => NAV.find((n) => n.id === id)?.label ?? id;

interface FocusCue {
  label: string;
  detail: string;
  page: PageId;
  tone: StatusTone;
}

/** "Where to focus next" — the through-line that routes the CFO from the hub to
 *  the page that explains each pressure point. Driven by control + plan signals. */
function buildFocusCues(
  k: CommandCenterKpis,
  hasActuals: boolean,
  readiness: ModelReadinessSummary | null,
): FocusCue[] {
  const cues: FocusCue[] = [];
  if (hasActuals && k.budget_revenue > 0 && k.actual_revenue < k.budget_revenue) {
    cues.push({
      label: 'Revenue behind plan',
      detail: `${formatSignedPercent((k.actual_revenue - k.budget_revenue) / k.budget_revenue)} vs budget`,
      page: 'financial',
      tone: 'adverse',
    });
  }
  if (k.nrr != null && k.nrr < 1) {
    cues.push({
      label: 'ARR retention below 100%',
      detail: `NRR ${formatPercent(k.nrr)} — see product & segment`,
      page: 'saas',
      tone: k.nrr < 0.97 ? 'adverse' : 'warning',
    });
  }
  if (k.cash_pressure > 0) {
    cues.push({
      label: 'Cash conversion under pressure',
      detail: `${formatGbpCompact(k.open_ar)} open AR · ${formatGbpCompact(k.cash_pressure)} pressure`,
      page: 'working-capital',
      tone: 'warning',
    });
  }
  if (k.revenue_governance_exceptions > 0 || k.deferred_exceptions > 0) {
    cues.push({
      label: 'Revenue recognition governance',
      detail: `${k.revenue_governance_exceptions} recognition exception${k.revenue_governance_exceptions === 1 ? '' : 's'} to review`,
      page: 'revenue',
      tone: 'warning',
    });
  }
  if (k.has_control_issue) {
    cues.push({
      label: 'Control exceptions to clear before sign-off',
      detail: `${k.control_issue_domains} domain${k.control_issue_domains === 1 ? '' : 's'} flagged`,
      page: 'control-tower',
      tone: 'warning',
    });
  }
  if (readiness && readiness.blocked_months > 0) {
    cues.push({
      label: 'Model-blocking periods in the actuals feed',
      detail: `${formatCount(readiness.blocked_months)} blocked month${readiness.blocked_months === 1 ? '' : 's'} · latest import-ready ${readiness.latest_excel_month_label ?? '-'}`,
      page: 'model',
      tone: 'warning',
    });
  }
  const rank: Record<StatusTone, number> = { adverse: 0, warning: 1, 'on-plan': 2, neutral: 3, favourable: 4 };
  return cues.sort((a, b) => rank[a.tone] - rank[b.tone]);
}

export function CfoCommandCenter({ onNavigate }: { onNavigate: (page: PageId) => void }) {
  const months = useQuery(getReportingMonths, []);
  const trend = useQuery(getRevenueTrend, []);
  const readiness = useQuery(getModelReadinessSummary, []);
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

  const focusCues = buildFocusCues(k, hasActuals, readiness.data ?? null);
  const latestActualMonth = [...monthOptions].reverse().find((m) => m.has_actuals) ?? null;
  const latestPlanMonth = monthOptions[monthOptions.length - 1] ?? null;
  const r = readiness.data ?? null;
  const readinessTone: StatusTone = !r ? 'neutral' : r.blocked_months > 0 ? 'warning' : 'favourable';

  return (
    <>
      <TopBar
        title="CFO Command Center"
        subtitle="How is the business performing, are we on plan, where are the risks?"
        actions={
          <>
            <span className="scope-pill">Scope: Company Total</span>
            <span className="scope-pill">Actuals to {latestActualMonth?.month_label ?? '-'}</span>
            <span className="scope-pill">Plan to {latestPlanMonth?.month_label ?? '-'}</span>
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

      {/* Executive summary leads the page — the CFO reads before scanning. */}
      <div className="narrative lead">
        <h3>Executive summary · {k.month_label}</h3>
        <p>{narrative}</p>
      </div>

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

      {/* Where to focus next — the page's visual anchor and routing layer */}
      {focusCues.length > 0 && (
        <div className="panel hero" style={{ marginBottom: 22, paddingBottom: 14 }}>
          <div className="panel-head">
            <div>
              <h3>Focus next</h3>
              <p className="panel-sub">Ranked by control and plan signals · each row routes to the page that explains it</p>
            </div>
          </div>
          <div className="focus-list">
            {focusCues.map((c) => (
              <button
                key={`${c.page}-${c.label}`}
                type="button"
                className={`focus-row tone-${c.tone}`}
                onClick={() => onNavigate(c.page)}
              >
                <span className="focus-label">{c.label}</span>
                <span className="focus-detail">{c.detail}</span>
                <span className="focus-go">{pageLabel(c.page)} →</span>
              </button>
            ))}
          </div>
        </div>
      )}

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
                contentStyle={{ background: '#ffffff', border: '1px solid #d6d3cb', borderRadius: 8, color: '#1a1a1a' }}
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
              {latestActualMonth && (
                <ReferenceLine
                  x={latestActualMonth.month_label}
                  stroke={AXIS}
                  strokeDasharray="4 4"
                  label={{ value: 'plan →', position: 'insideTopRight', fill: AXIS, fontSize: 10 }}
                />
              )}
              <Line type="monotone" dataKey="actual_revenue" stroke={ACCENT} strokeWidth={2.5} dot={false} connectNulls={false} />
              <Line type="monotone" dataKey="budget_revenue" stroke={AXIS} strokeWidth={1.5} strokeDasharray="5 4" dot={false} />
              <Line type="monotone" dataKey="forecast_revenue" stroke={INFO} strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Variance by driver"
          subtitle="Department and account analysis is available in the governed financial mart"
        >
          <div className="drillthrough-panel">
            <p>Review the largest favourable and adverse drivers behind the company result.</p>
            <button type="button" className="drillthrough-link" onClick={() => onNavigate('financial')}>
              Open Financial Performance →
            </button>
            <p className="src"><code>mart_financial_performance</code> · department × account</p>
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
          to="saas"
          onNavigate={onNavigate}
        />
        <DomainTile
          title="Working Capital"
          primary={formatGbpCompact(k.net_working_capital)}
          primaryLabel="Net AR less AP"
          secondary={`AR ${formatGbpCompact(k.open_ar)} · AP ${formatGbpCompact(k.open_ap)}`}
          source="mart_o2c · mart_ap_working_capital_control"
          tone="neutral"
          to="working-capital"
          onNavigate={onNavigate}
        />
        <DomainTile
          title="Workforce Cost"
          primary={formatGbpCompact(k.payroll_cost)}
          primaryLabel="Monthly payroll"
          secondary={`${formatCount(k.headcount)} active headcount`}
          source="mart_workforce_cost_control"
          tone="neutral"
          to="workforce"
          onNavigate={onNavigate}
        />
        <DomainTile
          title="Controls"
          primary={k.has_control_issue ? `${k.control_issue_domains} flagged` : 'Clean'}
          primaryLabel="Control exceptions"
          secondary={k.has_control_issue ? 'Review Control Tower' : 'No exceptions this month'}
          source="control marts"
          tone={k.has_control_issue ? 'adverse' : 'favourable'}
          to="control-tower"
          onNavigate={onNavigate}
        />
        <DomainTile
          title="Model Readiness"
          primary={!r ? '—' : r.blocked_months > 0 ? `${formatCount(r.blocked_months)} blocked` : 'Ready'}
          primaryLabel="Actuals feed for the CFO model"
          secondary={
            r
              ? `${formatCount(r.excel_actual_months)} import-ready months to ${r.latest_excel_month_label ?? '-'} · ${formatCount(r.review_months)} usable with review`
              : 'Loading model-serving feed'
          }
          source="mart_model_actuals_feed"
          tone={readinessTone}
          to="model"
          onNavigate={onNavigate}
        />
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
  to?: PageId;
  onNavigate?: (page: PageId) => void;
}

function DomainTile({ title, primary, primaryLabel, secondary, source, tone, to, onNavigate }: DomainTileProps) {
  const clickable = !!to && !!onNavigate;
  const inner = (
    <>
      <div className="tile-title">{title}</div>
      <div className="tile-primary">{primary}</div>
      <div className="tile-primary-label">{primaryLabel}</div>
      <div className="tile-secondary">{secondary}</div>
      <div className="tile-source">{source}</div>
      {clickable && <div className="tile-go">{pageLabel(to!)} →</div>}
    </>
  );
  return clickable ? (
    <button type="button" className={`tile tone-${tone} tile-clickable`} onClick={() => onNavigate!(to!)}>
      {inner}
    </button>
  ) : (
    <div className={`tile tone-${tone}`}>{inner}</div>
  );
}
