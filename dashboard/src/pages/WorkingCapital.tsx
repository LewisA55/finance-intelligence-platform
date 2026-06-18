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
  getTopArCustomers,
  getArCollections,
} from '../duckdb/queries';
import { TopBar } from '../components/TopBar';
import { KpiCard } from '../components/KpiCard';
import { ChartCard } from '../components/ChartCard';
import { StatusPill } from '../components/StatusPill';
import { chart } from '../lib/theme';
import { formatGbp, formatGbpCompact, formatPercent, formatCount } from '../lib/format';

const GRID = chart.grid;
const AXIS = chart.axis;
const collectionRateDomain: [number, (max: number) => number] = [
  0,
  (max) => Math.max(1, Math.ceil(max * 20) / 20),
];

export function WorkingCapital() {
  const position = useQuery(getWorkingCapitalPosition, []);
  const trend = useQuery(getArCollectionsTrend, []);
  const ageing = useQuery(getApAgeing, []);
  const vendors = useQuery(getTopVendorsAp, []);
  const arCustomers = useQuery(getTopArCustomers, []);
  const arCollections = useQuery(getArCollections, []);

  const p = position.data;

  // Collection rate (FYTD) = collected / billed, aggregated by region and segment.
  const collByDim = (key: 'region' | 'customer_segment', keep?: string[]) => {
    const rows = arCollections.data ?? [];
    const m = new Map<string, { name: string; billed: number; collected: number }>();
    for (const r of rows) {
      const name = r[key];
      if (keep && !keep.includes(name)) continue;
      const e = m.get(name) ?? { name, billed: 0, collected: 0 };
      e.billed += r.billed;
      e.collected += r.collected;
      m.set(name, e);
    }
    return Array.from(m.values())
      .map((e) => ({ name: e.name, rate: e.billed > 0 ? e.collected / e.billed : 0 }))
      .sort((a, b) => b.rate - a.rate);
  };
  const collByRegion = useMemo(() => collByDim('region'), [arCollections.data]);
  const collBySegment = useMemo(
    () => collByDim('customer_segment', ['Enterprise', 'Mid-Market', 'SMB']),
    [arCollections.data],
  );

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
    const topCustomer = arCustomers.data?.[0];
    const weakestRegion = collByRegion.length ? collByRegion[collByRegion.length - 1] : null;
    const a = ageing.data;
    const overdueShare = a && a.open_ap > 0 ? (a.d61_90 + a.d90_plus) / a.open_ap : null;
    return (
      `As at ${p.month_label}, open accounts receivable stands at ${formatGbp(p.open_ar)} against ` +
      `open payables of ${formatGbp(p.open_ap)}, a net working-capital position of ${formatGbp(p.net_wc)}. ` +
      `On receivables, collection runs at ${formatPercent(p.collection_rate)} overall` +
      `${weakestRegion ? `, weakest in ${weakestRegion.name} (${formatPercent(weakestRegion.rate)})` : ''}` +
      `${topCustomer ? `, with ${topCustomer.customer_name} carrying the largest open exposure (${formatGbp(topCustomer.open_ar)})` : ''}. ` +
      `On payables, ${formatGbp(p.overdue_ap)} is overdue` +
      `${overdueShare != null ? ` (${formatPercent(overdueShare)} of open AP is 60+ days past due)` : ''}` +
      `${topVendor ? `, concentrated in ${topVendor.vendor_name} (${formatGbp(topVendor.overdue_ap)} overdue, ${formatCount(topVendor.max_dpd)} days past due)` : ''}. ` +
      `All figures are governed Company-Total.`
    );
  }, [p, vendors.data, ageing.data, arCustomers.data, collByRegion]);

  const anyError =
    position.error || trend.error || ageing.error || vendors.error || arCustomers.error || arCollections.error;
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

      {/* Accounts receivable — collection performance */}
      <div className="panel-grid" style={{ marginTop: 12 }}>
        <ChartCard title="Collection rate by region" subtitle="FYTD collected / billed">
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={collByRegion} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="name" stroke={AXIS} fontSize={11} tickLine={false} />
              <YAxis stroke={AXIS} fontSize={11} tickLine={false} width={48} domain={collectionRateDomain} tickFormatter={(v: number) => formatPercent(v, 0)} />
              <Tooltip cursor={{ fill: 'rgba(0,0,0,0.03)' }} contentStyle={{ background: '#ffffff', border: '1px solid #d6d3cb', borderRadius: 8, color: '#1a1a1a' }} formatter={(v: number) => [formatPercent(v), 'Collection rate']} />
              <Bar dataKey="rate" fill={chart.primary} radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
        <ChartCard title="Collection rate by segment" subtitle="FYTD collected / billed">
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={collBySegment} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="name" stroke={AXIS} fontSize={11} tickLine={false} />
              <YAxis stroke={AXIS} fontSize={11} tickLine={false} width={48} domain={collectionRateDomain} tickFormatter={(v: number) => formatPercent(v, 0)} />
              <Tooltip cursor={{ fill: 'rgba(0,0,0,0.03)' }} contentStyle={{ background: '#ffffff', border: '1px solid #d6d3cb', borderRadius: 8, color: '#1a1a1a' }} formatter={(v: number) => [formatPercent(v), 'Collection rate']} />
              <Bar dataKey="rate" fill={chart.secondary} radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <div className="panel" style={{ marginTop: 12, paddingBottom: 16 }}>
        <div className="panel-head">
          <div>
            <h3>Top customers by open AR</h3>
            <p className="panel-sub">{p.month_label} · open receivable exposure</p>
          </div>
        </div>
        <div className="table-scroll">
        <table className="pnl">
          <thead>
            <tr>
              <th className="row-label">Customer</th>
              <th className="row-label">Segment</th>
              <th className="row-label">Region</th>
              <th>Open AR</th>
              <th>Overdue invoices</th>
            </tr>
          </thead>
          <tbody>
            {(arCustomers.data ?? []).map((c, i) => (
              <tr key={`${c.customer_name}-${i}`}>
                <td className="row-label">{c.customer_name}</td>
                <td className="row-label">{c.customer_segment}</td>
                <td className="row-label">{c.region}</td>
                <td>{formatGbp(c.open_ar)}</td>
                <td className={c.overdue_invoices > 0 ? 'adv' : ''}>{formatCount(c.overdue_invoices)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
        <p className="pnl-note">
          AR ageing buckets are not shipped in this dashboard slice: the O2C mart carries open exposure
          and overdue/disputed invoice counts, not GBP-aged buckets. AP ageing (above) uses bucketed
          snapshot data, so it is shown in true ageing bands.
        </p>
      </div>

      <div className="panel" style={{ marginTop: 12, paddingBottom: 16 }}>
        <div className="panel-head">
          <div>
            <h3>Top vendors by overdue AP</h3>
            <p className="panel-sub">{p.month_label} · open vs overdue payable · days past due</p>
          </div>
        </div>
        <div className="table-scroll">
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
      </div>

      <div className="narrative">
        <h3>Working-capital commentary</h3>
        <p>{narrative}</p>
      </div>
    </>
  );
}
