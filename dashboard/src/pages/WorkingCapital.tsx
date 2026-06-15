import { useMemo } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { useQuery } from '../hooks/useQuery';
import {
  getWorkingCapitalPosition,
  getArCollectionsTrend,
  getApAgeing,
  getTopVendorsAp,
} from '../duckdb/queries';
import { TopBar } from '../components/TopBar';
import { KpiCard } from '../components/KpiCard';
import { ChartCard } from '../components/ChartCard';
import { StatusPill } from '../components/StatusPill';
import { chart } from '../lib/theme';
import { formatGbp, formatGbpCompact, formatPercent, formatCount } from '../lib/format';

const GRID = chart.grid;
const AXIS = chart.axis;

export function WorkingCapital() {
  const position = useQuery(getWorkingCapitalPosition, []);
  const trend = useQuery(getArCollectionsTrend, []);
  const ageing = useQuery(getApAgeing, []);
  const vendors = useQuery(getTopVendorsAp, []);

  const p = position.data;

  const ageingData = useMemo(() => {
    const a = ageing.data;
    if (!a) return [];
    return [
      { bucket: 'Current', amount: a.current_amt, tone: 'current' },
      { bucket: '1–30', amount: a.d1_30, tone: 'mild' },
      { bucket: '31–60', amount: a.d31_60, tone: 'mild' },
      { bucket: '61–90', amount: a.d61_90, tone: 'severe' },
      { bucket: '90+', amount: a.d90_plus, tone: 'severe' },
    ];
  }, [ageing.data]);

  const narrative = useMemo(() => {
    if (!p) return '';
    const topVendor = vendors.data?.[0];
    const a = ageing.data;
    const overdueShare = a && a.open_ap > 0 ? (a.d61_90 + a.d90_plus) / a.open_ap : null;
    return (
      `As at ${p.month_label}, open accounts receivable stands at ${formatGbp(p.open_ar)} against ` +
      `open payables of ${formatGbp(p.open_ap)}, a net working-capital position of ${formatGbp(p.net_wc)}. ` +
      `${formatGbp(p.overdue_ap)} of AP is overdue` +
      `${overdueShare != null ? ` (${formatPercent(overdueShare)} of open AP is 60+ days past due)` : ''}` +
      `${topVendor ? `, concentrated in ${topVendor.vendor_name} (${formatGbp(topVendor.overdue_ap)} overdue, ${formatCount(topVendor.max_dpd)} days past due)` : ''}. ` +
      `All figures are governed Company-Total.`
    );
  }, [p, vendors.data, ageing.data]);

  const anyError = position.error || trend.error || ageing.error || vendors.error;
  if (anyError) {
    return <div className="error-box"><strong>Could not load data.</strong><div>{anyError.message}</div></div>;
  }
  if (!p) {
    return (
      <div className="state">
        <div className="spinner" />
        <div>Loading working-capital position…</div>
      </div>
    );
  }

  const bucketFill = (tone: string) =>
    tone === 'severe' ? chart.adverse : tone === 'mild' ? chart.amber : chart.secondary;

  return (
    <>
      <TopBar
        title="Working Capital"
        subtitle="Order-to-cash & accounts-payable position"
        actions={
          <>
            <span className="scope-pill">Scope: Company Total</span>
            <span className="scope-pill">As at {p.month_label}</span>
          </>
        }
      />

      <div className="kpi-grid">
        <KpiCard
          label="Open AR Exposure"
          value={formatGbpCompact(p.open_ar)}
          sub={`collection rate ${formatPercent(p.collection_rate)}`}
          status={{ tone: 'neutral', label: 'Monitor' }}
        />
        <KpiCard
          label="Open AP Liability"
          value={formatGbpCompact(p.open_ap)}
          sub={`as at ${p.month_label}`}
          status={{ tone: 'neutral', label: 'Monitor' }}
        />
        <KpiCard
          label="Net Working Capital"
          value={formatGbpCompact(p.net_wc)}
          sub="AR less AP"
          status={{ tone: 'neutral' }}
        />
        <KpiCard
          label="Overdue AP"
          value={formatGbpCompact(p.overdue_ap)}
          sub={p.overdue_ap > 0 ? 'past due — review' : 'none'}
          status={{ tone: p.overdue_ap > 0 ? 'adverse' : 'favourable', label: p.overdue_ap > 0 ? 'Overdue' : 'Clean' }}
        />
        <KpiCard
          label="Cash Pressure"
          value={formatGbpCompact(p.cash_pressure)}
          sub="heuristic indicator"
          status={{ tone: 'neutral', label: 'Monitor' }}
        />
      </div>

      <div className="panel-grid">
        <ChartCard
          title="AR exposure vs cash collected"
          subtitle="Company-total by month (GBP) — receivables build as collections lag"
        >
          <ResponsiveContainer width="100%" height={290}>
            <LineChart data={trend.data ?? []} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="month_label" stroke={AXIS} fontSize={11} tickLine={false} />
              <YAxis stroke={AXIS} fontSize={11} tickLine={false} width={56} tickFormatter={(v: number) => formatGbpCompact(v)} />
              <Tooltip
                contentStyle={{ background: '#ffffff', border: '1px solid #d6d3cb', borderRadius: 8, color: '#1a1a1a' }}
                formatter={(v: number, name) => [formatGbp(v), name === 'open_ar' ? 'Open AR' : 'Cash collected']}
              />
              <Legend formatter={(v) => (v === 'open_ar' ? 'Open AR' : 'Cash collected')} />
              <Line type="monotone" dataKey="open_ar" stroke={chart.primary} strokeWidth={2.5} dot={false} />
              <Line type="monotone" dataKey="cash_collected" stroke={chart.secondary} strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="AP ageing" subtitle={`Open payables by bucket · ${p.month_label}`}>
          <ResponsiveContainer width="100%" height={290}>
            <BarChart data={ageingData} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="bucket" stroke={AXIS} fontSize={11} tickLine={false} />
              <YAxis stroke={AXIS} fontSize={11} tickLine={false} width={52} tickFormatter={(v: number) => formatGbpCompact(v)} />
              <Tooltip
                cursor={{ fill: 'rgba(0,0,0,0.03)' }}
                contentStyle={{ background: '#ffffff', border: '1px solid #d6d3cb', borderRadius: 8, color: '#1a1a1a' }}
                formatter={(v: number) => [formatGbp(v), 'Open payable']}
              />
              <Bar dataKey="amount" radius={[2, 2, 0, 0]}>
                {ageingData.map((d) => (
                  <Cell key={d.bucket} fill={bucketFill(d.tone)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <div className="panel" style={{ marginTop: 12, paddingBottom: 16 }}>
        <div className="panel-head">
          <div>
            <h3>Top vendors by overdue AP</h3>
            <p className="panel-sub">{p.month_label} · open vs overdue payable · days past due</p>
          </div>
        </div>
        <table className="pnl">
          <thead>
            <tr>
              <th className="row-label">Vendor</th>
              <th className="row-label">Category</th>
              <th>Open AP</th>
              <th>Overdue</th>
              <th>Days past due</th>
              <th className="row-label">Status</th>
            </tr>
          </thead>
          <tbody>
            {(vendors.data ?? []).map((v) => (
              <tr key={v.vendor_name}>
                <td className="row-label">{v.vendor_name}</td>
                <td className="row-label">{v.vendor_category}</td>
                <td>{formatGbp(v.open_ap)}</td>
                <td className={v.overdue_ap > 0 ? 'adv' : ''}>{formatGbp(v.overdue_ap)}</td>
                <td>{formatCount(v.max_dpd)}</td>
                <td className="row-label">
                  <StatusPill
                    tone={v.critical ? 'adverse' : v.overdue_ap > 0 ? 'on-plan' : 'favourable'}
                    label={v.critical ? 'Critical' : v.overdue_ap > 0 ? 'Overdue' : 'Current'}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="narrative">
        <h3>Working-capital commentary</h3>
        <p>{narrative}</p>
      </div>
    </>
  );
}
