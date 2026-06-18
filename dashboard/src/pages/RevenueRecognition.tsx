import { useMemo } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  AreaChart,
  Area,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { useQuery } from '../hooks/useQuery';
import { getRevenueKpis, getRevRecTrend } from '../duckdb/queries';
import { TopBar } from '../components/TopBar';
import { KpiCard } from '../components/KpiCard';
import { ChartCard } from '../components/ChartCard';
import { chart } from '../lib/theme';
import { formatGbp, formatGbpCompact } from '../lib/format';

const GRID = chart.grid;
const AXIS = chart.axis;

export function RevenueRecognition() {
  const kpis = useQuery(getRevenueKpis, []);
  const trend = useQuery(getRevRecTrend, []);

  const k = kpis.data;

  const narrative = useMemo(() => {
    if (!k) return '';
    const t = trend.data ?? [];
    const yearEndDeferred = t.length ? t[t.length - 1].closing_deferred : k.closing_deferred;
    return (
      `As at ${k.month_label}, ${formatGbp(k.billed)} was billed and ${formatGbp(k.recognised_actual)} recognised, ` +
      `leaving ${formatGbp(k.closing_deferred)} of deferred revenue on the balance sheet. ` +
      `That backlog is scheduled to draw down to ${formatGbp(yearEndDeferred)} by year-end as already-billed revenue is earned. ` +
      `Commercial ARR is ${formatGbp(k.active_arr)}, but it is a live subscription run-rate rather than an accounting revenue measure and is not directly reconciled to this month's recognised revenue. ` +
      `${k.revenue_governance_exceptions > 0 || k.deferred_exceptions > 0 ? `Governance flagged ${k.revenue_governance_exceptions} recognition and ${k.deferred_exceptions} deferred-control exceptions.` : 'No recognition or deferred-control exceptions were flagged.'}`
    );
  }, [k, trend.data]);

  if (kpis.error || trend.error) {
    const msg = (kpis.error || trend.error)?.message;
    return <div className="error-box"><strong>Could not load data.</strong><div>{msg}</div></div>;
  }
  if (!k) {
    return (
      <div className="state">
        <div className="spinner" />
        <div>Loading revenue recognition…</div>
      </div>
    );
  }

  return (
    <>
      <TopBar
        title="Revenue Recognition"
        subtitle="Billed vs recognised revenue & deferred revenue control"
        actions={
          <>
            <span className="scope-pill">Scope: Company Total</span>
            <span className="scope-pill">As at {k.month_label}</span>
          </>
        }
      />

      <div className="kpi-grid">
        <KpiCard label="Billed Revenue" value={formatGbpCompact(k.billed)} sub={`${k.month_label} · monthly`} />
        <KpiCard
          label="Recognised Revenue"
          value={formatGbpCompact(k.recognised_actual)}
          sub={`${k.month_label} · earned in period`}
          status={{ tone: 'neutral' }}
        />
        <KpiCard
          label="Recognition Variance"
          value={formatGbpCompact(k.recognition_variance)}
          sub="actual less scheduled"
          status={{ tone: Math.abs(k.recognition_variance) > 1 ? 'warning' : 'favourable', label: Math.abs(k.recognition_variance) > 1 ? 'Review' : 'Clean' }}
        />
        <KpiCard
          label="Closing Deferred"
          value={formatGbpCompact(k.closing_deferred)}
          sub="balance-sheet liability"
          status={{ tone: 'neutral', label: 'Balance' }}
        />
        <KpiCard
          label="Recognition Exceptions"
          value={formatGbpCompact(k.unscheduled_leakage)}
          sub={`${k.revenue_governance_exceptions} governance flags`}
          status={{ tone: k.revenue_governance_exceptions > 0 ? 'warning' : 'favourable', label: k.revenue_governance_exceptions > 0 ? 'Review' : 'Clean' }}
        />
        <KpiCard
          label="Deferred Control"
          value={k.deferred_exceptions > 0 ? `${k.deferred_exceptions} flags` : 'Clean'}
          sub="rollforward continuity"
          status={{ tone: k.deferred_exceptions > 0 ? 'warning' : 'favourable', label: k.deferred_exceptions > 0 ? 'Review' : 'Clean' }}
        />
      </div>

      <div className="panel-grid">
        <ChartCard
          title="Billed vs recognised revenue"
          subtitle="Monthly (GBP) — bars billed · line recognised (actual) · dashed scheduled recognition"
        >
          <ResponsiveContainer width="100%" height={290}>
            <ComposedChart data={trend.data ?? []} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="month_label" stroke={AXIS} fontSize={11} tickLine={false} />
              <YAxis stroke={AXIS} fontSize={11} tickLine={false} width={56} tickFormatter={(v: number) => formatGbpCompact(v)} />
              <Tooltip
                cursor={{ fill: 'rgba(0,0,0,0.03)' }}
                contentStyle={{ background: '#ffffff', border: '1px solid #d6d3cb', borderRadius: 8, color: '#1a1a1a' }}
                formatter={(v: number, name) => {
                  const labels: Record<string, string> = {
                    billed: 'Billed',
                    recognised_actual: 'Recognised (actual)',
                    recognised_total: 'Recognised (incl. scheduled)',
                  };
                  return [formatGbp(v), labels[name as string] ?? name];
                }}
              />
              <Legend
                formatter={(v) =>
                  ({ billed: 'Billed', recognised_actual: 'Recognised (actual)', recognised_total: 'Scheduled recognition' }[
                    v as string
                  ] ?? v)
                }
              />
              <Bar dataKey="billed" fill={chart.budget} radius={[2, 2, 0, 0]} />
              <Line type="monotone" dataKey="recognised_actual" stroke={chart.primary} strokeWidth={2.5} dot={false} connectNulls={false} />
              <Line type="monotone" dataKey="recognised_total" stroke={chart.secondary} strokeWidth={1.5} strokeDasharray="5 4" dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Deferred revenue balance" subtitle="Closing deferred by month (GBP) — built then released as billed revenue is earned">
          <ResponsiveContainer width="100%" height={290}>
            <AreaChart data={trend.data ?? []} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
              <defs>
                <linearGradient id="defFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={chart.primary} stopOpacity={0.25} />
                  <stop offset="100%" stopColor={chart.primary} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="month_label" stroke={AXIS} fontSize={11} tickLine={false} />
              <YAxis stroke={AXIS} fontSize={11} tickLine={false} width={56} tickFormatter={(v: number) => formatGbpCompact(v)} />
              <Tooltip
                contentStyle={{ background: '#ffffff', border: '1px solid #d6d3cb', borderRadius: 8, color: '#1a1a1a' }}
                formatter={(v: number) => [formatGbp(v), 'Closing deferred']}
              />
              <Area type="monotone" dataKey="closing_deferred" stroke={chart.primary} strokeWidth={2} fill="url(#defFill)" />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <div className="panel-grid" style={{ marginTop: 12 }}>
        <div className="panel" style={{ paddingBottom: 16 }}>
          <div className="panel-head">
            <div>
              <h3>Deferred revenue rollforward</h3>
              <p className="panel-sub">{k.month_label} · opening to closing (GBP)</p>
            </div>
          </div>
          <div className="table-scroll">
          <table className="pnl">
            <tbody>
              <tr><td className="row-label">Opening deferred</td><td>{formatGbp(k.opening_deferred)}</td></tr>
              <tr><td className="row-label">+ New billings deferred</td><td className="fav">{formatGbp(k.new_billings_deferred)}</td></tr>
              <tr><td className="row-label">− Recognised in period</td><td className="adv">{formatGbp(k.recognised_deferred)}</td></tr>
              <tr className="total"><td className="row-label">Closing deferred</td><td>{formatGbp(k.closing_deferred)}</td></tr>
            </tbody>
          </table>
          </div>
        </div>

        <div className="panel" style={{ paddingBottom: 16 }}>
          <div className="panel-head">
            <div>
              <h3>Commercial vs accounting</h3>
              <p className="panel-sub">Related measures with deliberately different bases</p>
            </div>
          </div>
          <div className="table-scroll">
          <table className="pnl">
            <tbody>
              <tr><td className="row-label">Active ARR (commercial run-rate)</td><td>{formatGbp(k.active_arr)}</td></tr>
              <tr><td className="row-label">Active MRR (commercial run-rate)</td><td>{formatGbp(k.active_mrr)}</td></tr>
              <tr className="total"><td className="row-label">Recognised revenue (earned in month)</td><td>{formatGbp(k.recognised_actual)}</td></tr>
            </tbody>
          </table>
          </div>
          <p className="pnl-note">
            ARR/MRR describe the current subscription run-rate. Recognised revenue is the earned
            accounting amount across subscription, services and legacy streams. They are shown
            together for context, not as a direct reconciliation.
          </p>
        </div>
      </div>

      <div className="narrative">
        <h3>Revenue recognition commentary</h3>
        <p>{narrative}</p>
      </div>
    </>
  );
}
