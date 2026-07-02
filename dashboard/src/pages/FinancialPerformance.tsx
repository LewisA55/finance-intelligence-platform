import { useEffect, useMemo, useState } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  LineChart,
  Line,
  Legend,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from 'recharts';
import { useQuery } from '../hooks/useQuery';
import {
  getReportingMonths,
  getFinancialSummary,
  getDepartmentVariance,
  getTopAccountVariances,
  getRevenueTrend,
  getModelActualsFeed,
} from '../duckdb/queries';
import { TopBar } from '../components/TopBar';
import { KpiCard } from '../components/KpiCard';
import { ChartCard } from '../components/ChartCard';
import { StatusPill, type StatusTone } from '../components/StatusPill';
import { chart } from '../lib/theme';
import { formatGbp, formatGbpCompact, formatSignedPercent } from '../lib/format';
import type { PageId } from '../nav';

const GRID = chart.grid;
const AXIS = chart.axis;

function favTone(favourable: boolean): StatusTone {
  return favourable ? 'favourable' : 'adverse';
}

type ClassFilter = 'All' | 'Revenue' | 'Expense';
type FavFilter = 'All' | 'Favourable' | 'Adverse';

export function FinancialPerformance({ onNavigate }: { onNavigate: (page: PageId) => void }) {
  const months = useQuery(getReportingMonths, []);
  const trend = useQuery(getRevenueTrend, []);
  const feed = useQuery(getModelActualsFeed, []);
  const [selected, setSelected] = useState<string | null>(null);
  const [classFilter, setClassFilter] = useState<ClassFilter>('All');
  const [favFilter, setFavFilter] = useState<FavFilter>('All');

  useEffect(() => {
    if (selected || !months.data || months.data.length === 0) return;
    const withActuals = months.data.filter((m) => m.has_actuals);
    const latest =
      withActuals.length > 0
        ? withActuals[withActuals.length - 1]
        : months.data[months.data.length - 1];
    setSelected(latest.month_iso);
  }, [months.data, selected]);

  const summary = useQuery(
    () => (selected ? getFinancialSummary(selected) : Promise.resolve(null)),
    [selected],
  );
  const deptVar = useQuery(
    () => (selected ? getDepartmentVariance(selected) : Promise.resolve([])),
    [selected],
  );
  const topVar = useQuery(
    () => (selected ? getTopAccountVariances(selected) : Promise.resolve([])),
    [selected],
  );

  const monthLabel =
    months.data?.find((m) => m.month_iso === selected)?.month_label ?? '';
  const s = summary.data;
  const hasActuals = !!s && (s.revenue_actual > 0 || s.opex_actual > 0);

  const operatingResult = s ? s.revenue_actual - s.opex_actual : 0;
  const budgetOperatingResult = s ? s.revenue_budget - s.opex_budget : 0;
  const operatingVariance = operatingResult - budgetOperatingResult;

  const narrative = useMemo(() => {
    if (!s) return '';
    if (!hasActuals) {
      return `${monthLabel} is a plan-only period — no financial actuals are recognised yet. Budget revenue is ${formatGbp(s.revenue_budget)} against budgeted operating expenses of ${formatGbp(s.opex_budget)}.`;
    }
    const rows = topVar.data ?? [];
    const adverse = rows
      .filter((r) => r.favourability === 'Adverse')
      .sort((a, b) => Math.abs(b.variance) - Math.abs(a.variance))[0];
    const favourable = rows
      .filter((r) => r.favourability === 'Favourable')
      .sort((a, b) => Math.abs(b.variance) - Math.abs(a.variance))[0];
    const revVar = s.revenue_actual - s.revenue_budget;
    return (
      `For ${monthLabel}, revenue of ${formatGbp(s.revenue_actual)} is ${formatSignedPercent(revVar / s.revenue_budget)} vs budget, ` +
      `with operating expenses of ${formatGbp(s.opex_actual)} (${formatSignedPercent((s.opex_actual - s.opex_budget) / s.opex_budget)} vs budget). ` +
      `The largest favourable line is ${favourable ? `${favourable.department} — ${favourable.account}` : 'n/a'}; ` +
      `${adverse ? `the main adverse line is ${adverse.department} — ${adverse.account}.` : 'no adverse lines were flagged.'} ` +
      `All figures are FC_BASE_CASE on a governed Company-Total basis.`
    );
  }, [s, hasActuals, monthLabel, topVar.data]);

  // Operating-result variance waterfall: revenue variance, then each
  // department's opex contribution (over-budget spend reduces the result).
  const waterfall = useMemo(() => {
    if (!s) return [];
    const items = [
      { name: 'Revenue', delta: s.revenue_actual - s.revenue_budget },
      ...(deptVar.data ?? []).map((d) => ({ name: d.department, delta: -d.variance })),
    ];
    let cumulative = 0;
    const rows = items.map((it) => {
      const base = it.delta >= 0 ? cumulative : cumulative + it.delta;
      cumulative += it.delta;
      return { name: it.name, base, size: Math.abs(it.delta), delta: it.delta, total: false };
    });
    rows.push({
      name: 'Operating result',
      base: Math.min(0, cumulative),
      size: Math.abs(cumulative),
      delta: cumulative,
      total: true,
    });
    return rows;
  }, [s, deptVar.data]);

  const feedRow = feed.data?.find((r) => r.month_iso === selected) ?? null;

  const anyError = months.error || summary.error || deptVar.error || topVar.error || trend.error || feed.error;
  if (anyError) {
    return <div className="error-box"><strong>Could not load data.</strong><div>{anyError.message}</div></div>;
  }
  if (!s) {
    return (
      <div className="state">
        <div className="spinner" />
        <div>Loading financial performance mart…</div>
      </div>
    );
  }

  const deptChartData = (deptVar.data ?? []).map((d) => ({
    department: d.department,
    variance: d.variance,
  }));

  const filteredVariances = (topVar.data ?? []).filter(
    (r) =>
      (classFilter === 'All' || r.account_class === classFilter) &&
      (favFilter === 'All' || r.favourability === favFilter),
  );

  return (
    <>
      <TopBar
        title="Financial Performance"
        subtitle="Why did the result move against plan — and which departments drove it?"
        actions={
          <>
            <span className="scope-pill">Scope: Company Total</span>
            <span className="scope-pill">Forecast: FC_BASE_CASE</span>
            <select
              className="month-select"
              value={selected ?? ''}
              onChange={(e) => setSelected(e.target.value)}
              aria-label="Reporting month"
            >
              {(months.data ?? []).map((m) => (
                <option key={m.month_iso} value={m.month_iso}>
                  {m.month_label}
                  {m.has_actuals ? '' : ' (plan)'}
                </option>
              ))}
            </select>
          </>
        }
      />

      <div className="kpi-grid">
        <KpiCard
          label="Revenue"
          value={hasActuals ? formatGbpCompact(s.revenue_actual) : '—'}
          sub={`vs ${formatGbpCompact(s.revenue_budget)} budget`}
          delta={
            hasActuals
              ? {
                  text: `${formatSignedPercent((s.revenue_actual - s.revenue_budget) / s.revenue_budget)} vs budget`,
                  direction: s.revenue_actual >= s.revenue_budget ? 'up' : 'down',
                }
              : undefined
          }
          status={hasActuals ? { tone: favTone(s.revenue_actual >= s.revenue_budget) } : { tone: 'neutral', label: 'Plan only' }}
        />
        <KpiCard
          label="Operating Expenses"
          value={hasActuals ? formatGbpCompact(s.opex_actual) : '—'}
          sub={`vs ${formatGbpCompact(s.opex_budget)} budget`}
          delta={
            hasActuals
              ? {
                  text: `${formatSignedPercent((s.opex_actual - s.opex_budget) / s.opex_budget)} vs budget`,
                  direction: s.opex_actual <= s.opex_budget ? 'up' : 'down',
                }
              : undefined
          }
          status={hasActuals ? { tone: favTone(s.opex_actual <= s.opex_budget) } : { tone: 'neutral', label: 'Plan only' }}
        />
        <KpiCard
          label="Operating Result"
          value={hasActuals ? formatGbpCompact(operatingResult) : '—'}
          sub={`vs ${formatGbpCompact(budgetOperatingResult)} budget`}
          status={hasActuals ? { tone: favTone(operatingResult >= budgetOperatingResult) } : { tone: 'neutral', label: 'Plan only' }}
        />
        <KpiCard
          label="Variance vs Budget"
          value={hasActuals ? `${operatingVariance > 0 ? '+' : ''}${formatGbpCompact(operatingVariance)}` : '—'}
          sub="operating result"
          status={hasActuals ? { tone: favTone(operatingVariance >= 0) } : { tone: 'neutral' }}
        />
      </div>

      <div className="panel-grid">
        <ChartCard
          title="Actual vs budget vs forecast"
          subtitle="Company-total revenue by month (GBP) · actuals stop at the last closed month"
        >
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={trend.data ?? []} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="month_label" stroke={AXIS} fontSize={11} tickLine={false} minTickGap={18} />
              <YAxis stroke={AXIS} fontSize={11} tickLine={false} width={56} tickFormatter={(v: number) => formatGbpCompact(v)} />
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
                  ({ actual_revenue: 'Actual', budget_revenue: 'Budget', forecast_revenue: 'Forecast' }[v as string] ?? v)
                }
              />
              {(() => {
                const lastActual = [...(months.data ?? [])].reverse().find((m) => m.has_actuals);
                return lastActual ? (
                  <ReferenceLine
                    x={lastActual.month_label}
                    stroke={AXIS}
                    strokeDasharray="4 4"
                    label={{ value: 'plan →', position: 'insideTopRight', fill: AXIS, fontSize: 10 }}
                  />
                ) : null;
              })()}
              <Line type="monotone" dataKey="actual_revenue" stroke={chart.primary} strokeWidth={2.5} dot={false} connectNulls={false} />
              <Line type="monotone" dataKey="budget_revenue" stroke={AXIS} strokeWidth={1.5} strokeDasharray="5 4" dot={false} />
              <Line type="monotone" dataKey="forecast_revenue" stroke={chart.secondary} strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <div className="panel">
          <div className="panel-head">
            <div>
              <h3>Model feed bridge</h3>
              <p className="panel-sub">How {monthLabel} lands in <code>mart_model_actuals_feed</code></p>
            </div>
            {feedRow && (
              <StatusPill
                tone={feedRow.readiness_status === 'Ready' ? 'favourable' : feedRow.readiness_status === 'Blocked' ? 'adverse' : feedRow.readiness_status === 'Usable with review' ? 'warning' : 'neutral'}
                label={feedRow.readiness_status}
              />
            )}
          </div>
          {feedRow ? (
            <ul className="kv">
              <li><span>Feed recognised revenue</span><strong>{formatGbp(feedRow.recognised_revenue)}</strong></li>
              <li><span>Feed operating expenses</span><strong>{formatGbp(feedRow.opex)}</strong></li>
              <li><span>Feed operating profit</span><strong>{formatGbp(feedRow.operating_profit)}</strong></li>
              <li><span>Excel import</span><strong>{feedRow.use_in_excel_actuals ? 'Included' : 'Excluded'}</strong></li>
            </ul>
          ) : (
            <p className="pnl-note">This month is outside the model-serving feed window.</p>
          )}
          <p className="pnl-note">
            The same governed actuals feed the CFO model — recognised revenue here is the
            accounting basis, not commercial ARR.
          </p>
          <button type="button" className="drillthrough-link" onClick={() => onNavigate('model')}>
            Open Forecast &amp; Valuation →
          </button>
        </div>
      </div>

      <div className="panel-grid">
        <ChartCard
          title="Operating expense variance vs budget by department"
          subtitle="Favourable = under budget (green) · adverse = over budget (burgundy)"
        >
          <ResponsiveContainer width="100%" height={300}>
            <BarChart
              data={deptChartData}
              layout="vertical"
              margin={{ top: 8, right: 16, left: 8, bottom: 0 }}
            >
              <CartesianGrid stroke={GRID} horizontal={false} />
              <XAxis type="number" stroke={AXIS} fontSize={11} tickLine={false} tickFormatter={(v: number) => formatGbpCompact(v)} />
              <YAxis type="category" dataKey="department" stroke={AXIS} fontSize={11} tickLine={false} width={92} />
              <Tooltip
                cursor={{ fill: 'rgba(0,0,0,0.03)' }}
                contentStyle={{ background: '#ffffff', border: '1px solid #d6d3cb', borderRadius: 8, color: '#1a1a1a' }}
                formatter={(v: number) => [formatGbp(v), 'Variance vs budget']}
              />
              <ReferenceLine x={0} stroke="#d6d3cb" />
              <Bar dataKey="variance" radius={[0, 2, 2, 0]}>
                {deptChartData.map((d) => (
                  <Cell key={d.department} fill={d.variance <= 0 ? chart.favourable : chart.adverse} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Revenue vs plan" subtitle={`${monthLabel} · GBP`}>
          <div className="rev-stat">
            <div className="rev-row">
              <span>Actual</span>
              <strong>{hasActuals ? formatGbp(s.revenue_actual) : '—'}</strong>
            </div>
            <div className="rev-row">
              <span>Budget</span>
              <strong>{formatGbp(s.revenue_budget)}</strong>
            </div>
            <div className="rev-row">
              <span>Forecast</span>
              <strong>{formatGbp(s.revenue_forecast)}</strong>
            </div>
            <div className="rev-row total">
              <span>Variance vs budget</span>
              <strong className={hasActuals ? (s.revenue_actual >= s.revenue_budget ? 'fav' : 'adv') : ''}>
                {hasActuals ? `${s.revenue_actual - s.revenue_budget > 0 ? '+' : ''}${formatGbp(s.revenue_actual - s.revenue_budget)}` : '—'}
              </strong>
            </div>
          </div>
        </ChartCard>
      </div>

      {hasActuals && waterfall.length > 1 && (
        <ChartCard
          title="Operating result variance waterfall"
          subtitle={`${monthLabel} · revenue variance and department opex contributions to the operating-result variance vs budget`}
        >
          <ResponsiveContainer width="100%" height={Math.max(220, waterfall.length * 34)}>
            <BarChart data={waterfall} layout="vertical" margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
              <CartesianGrid stroke={GRID} horizontal={false} />
              <XAxis type="number" stroke={AXIS} fontSize={11} tickLine={false} tickFormatter={(v: number) => formatGbpCompact(v)} />
              <YAxis type="category" dataKey="name" stroke={AXIS} fontSize={11} tickLine={false} width={130} />
              <Tooltip
                cursor={{ fill: 'rgba(0,0,0,0.03)' }}
                contentStyle={{ background: '#ffffff', border: '1px solid #d6d3cb', borderRadius: 8, color: '#1a1a1a' }}
                formatter={(v: number, name: string, entry) => {
                  if (name === 'base') return ['', ''];
                  const delta = (entry?.payload as { delta: number } | undefined)?.delta ?? v;
                  return [`${delta > 0 ? '+' : ''}${formatGbp(delta)}`, 'Contribution'];
                }}
              />
              <ReferenceLine x={0} stroke="#d6d3cb" />
              <Bar dataKey="base" stackId="wf" fill="transparent" />
              <Bar dataKey="size" stackId="wf" radius={[0, 2, 2, 0]}>
                {waterfall.map((w) => (
                  <Cell
                    key={w.name}
                    fill={w.total ? chart.primary : w.delta >= 0 ? chart.favourable : chart.adverse}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      )}

      <div className="panel" style={{ marginTop: 12, paddingBottom: 16 }}>
        <div className="panel-head">
          <div>
            <h3>Largest variances · department × account</h3>
            <p className="panel-sub">{monthLabel} · actual vs budget · FC_BASE_CASE</p>
          </div>
          <div className="seg-toggle-group">
            <div className="seg-toggle" role="group" aria-label="Account class filter">
              {(['All', 'Revenue', 'Expense'] as const).map((c) => (
                <button
                  key={c}
                  type="button"
                  className={`seg-btn${classFilter === c ? ' active' : ''}`}
                  onClick={() => setClassFilter(c)}
                >
                  {c === 'Expense' ? 'Opex' : c}
                </button>
              ))}
            </div>
            <div className="seg-toggle" role="group" aria-label="Favourability filter">
              {(['All', 'Favourable', 'Adverse'] as const).map((f) => (
                <button
                  key={f}
                  type="button"
                  className={`seg-btn${favFilter === f ? ' active' : ''}`}
                  onClick={() => setFavFilter(f)}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="table-scroll">
        <table className="pnl">
          <thead>
            <tr>
              <th className="row-label">Department</th>
              <th className="row-label">Account</th>
              <th>Actual</th>
              <th>Budget</th>
              <th>Var vs budget</th>
              <th className="row-label">Status</th>
            </tr>
          </thead>
          <tbody>
            {filteredVariances.map((r) => (
              <tr key={`${r.department}-${r.account}`}>
                <td className="row-label">{r.department}</td>
                <td className="row-label">{r.account}</td>
                <td>{formatGbp(r.actual)}</td>
                <td>{formatGbp(r.budget)}</td>
                <td className={r.favourability === 'Favourable' ? 'fav' : r.favourability === 'Adverse' ? 'adv' : ''}>
                  {r.variance > 0 ? '+' : ''}{formatGbp(r.variance)}
                </td>
                <td className="row-label">
                  {r.favourability && (
                    <StatusPill tone={r.favourability === 'Favourable' ? 'favourable' : 'adverse'} label={r.favourability} />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>

      <div className="narrative">
        <h3>Variance commentary</h3>
        <p>{narrative}</p>
      </div>
    </>
  );
}
