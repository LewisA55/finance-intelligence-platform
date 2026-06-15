import {
  ResponsiveContainer,
  AreaChart,
  Area,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { useQuery } from '../hooks/useQuery';
import { getExecutiveTrend } from '../duckdb/queries';
import { TopBar } from '../components/TopBar';
import { ChartCard } from '../components/ChartCard';
import { KpiCard } from '../components/KpiCard';
import { formatGbp, formatGbpCompact, formatPercent, formatCount } from '../lib/format';
import { chart } from '../lib/theme';

const ACCENT = chart.primary;
const INFO = chart.secondary;
const DANGER = chart.adverse;
const GRID = chart.grid;
const AXIS = chart.axis;

export function SaaSPerformance() {
  const { data, loading, error } = useQuery(getExecutiveTrend, []);

  if (loading) {
    return (
      <div className="state">
        <div className="spinner" />
        <div>Loading SaaS metrics…</div>
      </div>
    );
  }
  if (error) return <div className="error-box">{error.message}</div>;
  if (!data || data.length === 0) return <div className="state">No SaaS data.</div>;

  const latest = data[data.length - 1];

  return (
    <>
      <TopBar
        title="SaaS Performance"
        subtitle="Company-total ARR movement & retention · GBP"
        actions={<span className="scope-pill">Scope: Company Total</span>}
      />

      <div className="kpi-grid">
        <KpiCard label="Active ARR" value={formatGbpCompact(latest.active_arr_gbp)} sub={`as at ${latest.month_label}`} />
        <KpiCard label="Active MRR" value={formatGbpCompact(latest.active_mrr_gbp)} />
        <KpiCard label="Net Revenue Retention" value={formatPercent(latest.nrr)} sub="excl. new business" />
        <KpiCard label="Gross Revenue Retention" value={formatPercent(latest.grr)} />
        <KpiCard label="Active Customers" value={formatCount(latest.active_customers)} />
      </div>

      <div className="panel-grid">
        <ChartCard title="Active ARR trend" subtitle="Monthly run-rate ARR (GBP)">
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
              <defs>
                <linearGradient id="arrFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={ACCENT} stopOpacity={0.5} />
                  <stop offset="100%" stopColor={ACCENT} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="month_label" stroke={AXIS} fontSize={12} tickLine={false} />
              <YAxis
                stroke={AXIS}
                fontSize={12}
                tickLine={false}
                width={56}
                tickFormatter={(v: number) => formatGbpCompact(v)}
                domain={[(min: number) => min - 2_000_000, (max: number) => max + 2_000_000]}
              />
              <Tooltip
                contentStyle={{ background: '#16213a', border: '1px solid #243150', borderRadius: 10, color: '#e8eef9' }}
                formatter={(v: number) => [formatGbp(v), 'Active ARR']}
              />
              <Area type="monotone" dataKey="active_arr_gbp" stroke={ACCENT} strokeWidth={2} fill="url(#arrFill)" />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Retention" subtitle="NRR vs GRR (%)">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="month_label" stroke={AXIS} fontSize={12} tickLine={false} />
              <YAxis stroke={AXIS} fontSize={12} tickLine={false} width={48} domain={[0.9, 1.05]} tickFormatter={(v: number) => formatPercent(v, 0)} />
              <Tooltip
                contentStyle={{ background: '#16213a', border: '1px solid #243150', borderRadius: 10, color: '#e8eef9' }}
                formatter={(v: number, name) => [formatPercent(v), name === 'nrr' ? 'NRR' : 'GRR']}
              />
              <Legend formatter={(v) => (v === 'nrr' ? 'NRR' : 'GRR')} />
              <Line type="monotone" dataKey="nrr" stroke={ACCENT} strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="grr" stroke={INFO} strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <div style={{ marginTop: 16 }}>
        <ChartCard title="Monthly ARR movement" subtitle="New business & gross expansion vs gross churn (GBP)">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="month_label" stroke={AXIS} fontSize={12} tickLine={false} />
              <YAxis stroke={AXIS} fontSize={12} tickLine={false} width={56} tickFormatter={(v: number) => formatGbpCompact(v)} />
              <Tooltip
                contentStyle={{ background: '#16213a', border: '1px solid #243150', borderRadius: 10, color: '#e8eef9' }}
                formatter={(v: number, name) => {
                  const labels: Record<string, string> = {
                    new_business_arr_gbp: 'New business',
                    gross_expansion_arr_gbp: 'Gross expansion',
                    gross_churn_arr_gbp: 'Gross churn',
                  };
                  return [formatGbp(v), labels[name as string] ?? name];
                }}
              />
              <Legend
                formatter={(v) =>
                  ({ new_business_arr_gbp: 'New business', gross_expansion_arr_gbp: 'Gross expansion', gross_churn_arr_gbp: 'Gross churn' }[
                    v as string
                  ] ?? v)
                }
              />
              <Bar dataKey="new_business_arr_gbp" fill={ACCENT} radius={[3, 3, 0, 0]} />
              <Bar dataKey="gross_expansion_arr_gbp" fill={INFO} radius={[3, 3, 0, 0]} />
              <Bar dataKey="gross_churn_arr_gbp" fill={DANGER} radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </>
  );
}
