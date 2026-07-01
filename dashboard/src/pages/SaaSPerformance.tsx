import { useMemo } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
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
  getSaasKpis,
  getArrWalk,
  getArrByRegion,
  getExecutiveTrend,
  getArrByProductSegment,
  getArrMovementByProduct,
  getRetentionBySegment,
  getSaasIntelligenceTrend,
  getSaasProductTrend,
  getSaasSegmentTrend,
} from '../duckdb/queries';
import { TopBar } from '../components/TopBar';
import { KpiCard } from '../components/KpiCard';
import { ChartCard } from '../components/ChartCard';
import { StatusPill, type StatusTone } from '../components/StatusPill';
import { chart } from '../lib/theme';
import { formatGbp, formatGbpCompact, formatPercent, formatCount } from '../lib/format';

const GRID = chart.grid;
const AXIS = chart.axis;
const SEGMENTS = ['Enterprise', 'Mid-Market', 'SMB'] as const;
const SEG_FILL: Record<string, string> = {
  Enterprise: chart.primary,
  'Mid-Market': chart.secondary,
  SMB: chart.budget,
};
const PRODUCT_FILL: Record<string, string> = {
  Core: chart.primary,
  Analytics: chart.secondary,
  AI: chart.favourable,
  'Professional Services': chart.budget,
  Legacy: chart.adverse,
  Other: chart.axis,
};

interface WalkStep {
  name: string;
  base: number;
  value: number;
  amount: number;
  kind: 'total' | 'up' | 'down';
}

function nrrTone(v: number | null): StatusTone {
  if (v == null) return 'neutral';
  return v >= 1 ? 'favourable' : v >= 0.95 ? 'on-plan' : 'adverse';
}

export function SaaSPerformance() {
  const kpis = useQuery(getSaasKpis, []);
  const walk = useQuery(getArrWalk, []);
  const region = useQuery(getArrByRegion, []);
  const trend = useQuery(getExecutiveTrend, []);
  const prodSeg = useQuery(getArrByProductSegment, []);
  const prodMove = useQuery(getArrMovementByProduct, []);
  const segRet = useQuery(getRetentionBySegment, []);
  const longTrend = useQuery(getSaasIntelligenceTrend, []);
  const productTrend = useQuery(getSaasProductTrend, []);
  const segmentTrend = useQuery(getSaasSegmentTrend, []);

  const k = kpis.data;

  const walkSteps = useMemo<WalkStep[]>(() => {
    const w = walk.data;
    if (!w) return [];
    const steps: WalkStep[] = [];
    let running = w.opening;
    steps.push({ name: 'Opening', base: 0, value: w.opening, amount: w.opening, kind: 'total' });
    const up = (name: string, amt: number) => {
      steps.push({ name, base: running, value: amt, amount: amt, kind: 'up' });
      running += amt;
    };
    const down = (name: string, amt: number) => {
      running -= amt;
      steps.push({ name, base: running, value: amt, amount: -amt, kind: 'down' });
    };
    up('New', w.new_business);
    up('Expansion', w.expansion);
    up('Price', w.price_increase);
    down('Contraction', w.contraction);
    down('Churn', w.churn);
    down('Pause', w.pause);
    steps.push({ name: 'Closing', base: 0, value: w.closing, amount: w.closing, kind: 'total' });
    return steps;
  }, [walk.data]);

  // Pivot product-family × segment into stacked-bar rows.
  const prodSegData = useMemo(() => {
    const rows = prodSeg.data ?? [];
    const byProduct = new Map<string, Record<string, number | string>>();
    for (const r of rows) {
      if (!byProduct.has(r.product_family)) {
        byProduct.set(r.product_family, { product_family: r.product_family, Enterprise: 0, 'Mid-Market': 0, SMB: 0 });
      }
      byProduct.get(r.product_family)![r.customer_segment] = r.active_arr;
    }
    return Array.from(byProduct.values()).sort(
      (a, b) =>
        ((b.Enterprise as number) + (b['Mid-Market'] as number) + (b.SMB as number)) -
        ((a.Enterprise as number) + (a['Mid-Market'] as number) + (a.SMB as number)),
    );
  }, [prodSeg.data]);

  const productHistory = useMemo(() => {
    const rows = productTrend.data ?? [];
    const months = Array.from(new Set(rows.map((r) => r.month_iso))).slice(-36);
    const keep = new Set(months);
    const byMonth = new Map<string, Record<string, number | string>>();
    for (const r of rows) {
      if (!keep.has(r.month_iso)) continue;
      const row = byMonth.get(r.month_iso) ?? {
        month_iso: r.month_iso,
        month_label: r.month_label,
        Core: 0,
        Analytics: 0,
        AI: 0,
        'Professional Services': 0,
        Legacy: 0,
        Other: 0,
      };
      row[r.product_family] = ((row[r.product_family] as number) ?? 0) + r.active_arr;
      byMonth.set(r.month_iso, row);
    }
    return Array.from(byMonth.values()).sort((a, b) => String(a.month_iso).localeCompare(String(b.month_iso)));
  }, [productTrend.data]);

  const segmentHistory = useMemo(() => {
    const rows = segmentTrend.data ?? [];
    const months = Array.from(new Set(rows.map((r) => r.month_iso))).slice(-36);
    const keep = new Set(months);
    const byMonth = new Map<string, Record<string, number | string | null>>();
    for (const r of rows) {
      if (!keep.has(r.month_iso)) continue;
      const row = byMonth.get(r.month_iso) ?? {
        month_iso: r.month_iso,
        month_label: r.month_label,
        Enterprise: null,
        'Mid-Market': null,
        SMB: null,
      };
      row[r.customer_segment] = r.nrr;
      byMonth.set(r.month_iso, row);
    }
    return Array.from(byMonth.values()).sort((a, b) => String(a.month_iso).localeCompare(String(b.month_iso)));
  }, [segmentTrend.data]);

  const stepFill = (kind: WalkStep['kind']) =>
    kind === 'total' ? chart.primary : kind === 'up' ? chart.favourable : chart.adverse;

  const narrative = useMemo(() => {
    if (!k || !walk.data) return '';
    const w = walk.data;
    const netWalk = w.closing - w.opening;
    const direction = netWalk < 0 ? 'under modest pressure' : 'growing';
    const topRegion = region.data?.[0];
    const topProduct = prodMove.data?.[0]; // highest active ARR (query order)
    const worstNet = [...(prodMove.data ?? [])].sort((a, b) => a.net - b.net)[0];

    const segNrr = (segRet.data ?? [])
      .filter((s) => s.beginning_arr > 0)
      .map((s) => ({ seg: s.customer_segment, nrr: s.net_retained / s.beginning_arr }))
      .sort((a, b) => a.nrr - b.nrr);
    const spread = segNrr.length ? segNrr[segNrr.length - 1].nrr - segNrr[0].nrr : 0;
    const segClause =
      segNrr.length === 0
        ? ''
        : spread < 0.02
          ? `Monthly-cohort retention is broadly uniform by segment, so the pressure is product-led rather than segment-led. `
          : `Period-weighted monthly retention is weakest in ${segNrr[0].seg} (NRR ${formatPercent(segNrr[0].nrr)}). `;

    const productClause =
      topProduct && worstNet && worstNet.net < 0
        ? `The book is concentrated in ${topProduct.product_family}, and ${worstNet.product_family} saw the largest net ARR erosion (${formatGbp(worstNet.net)}). `
        : topProduct
          ? `The book is concentrated in ${topProduct.product_family}. `
          : '';

    return (
      `ARR is ${direction}: it moved ${formatGbp(netWalk)} FYTD to ${formatGbp(w.closing)} as churn (${formatGbp(w.churn)}) and pause (${formatGbp(w.pause)}) ` +
      `outweighed ${formatGbp(w.new_business + w.expansion)} of new and expansion across ${formatCount(k.ending_customers)} customers. ` +
      productClause +
      segClause +
      `${topRegion ? `${topRegion.region} remains the largest region at ${formatGbp(topRegion.active_arr)}.` : ''}`
    );
  }, [k, walk.data, region.data, segRet.data, prodMove.data]);

  const anyError =
    kpis.error || walk.error || region.error || trend.error || prodSeg.error || prodMove.error || segRet.error ||
    longTrend.error || productTrend.error || segmentTrend.error;
  if (anyError) {
    return <div className="error-box"><strong>Could not load data.</strong><div>{anyError.message}</div></div>;
  }
  if (!k || !walk.data) {
    return (
      <div className="state">
        <div className="spinner" />
        <div>Loading SaaS metrics…</div>
      </div>
    );
  }

  return (
    <>
      <TopBar
        title="SaaS Performance"
        subtitle="ARR movement, retention, product & segment mix"
        actions={
          <>
            <span className="scope-pill">Scope: Company Total</span>
            <span className="scope-pill">As at {k.month_label}</span>
          </>
        }
      />

      <div className="kpi-grid">
        <KpiCard label="Active ARR" value={formatGbpCompact(k.active_arr)} sub={`${formatGbpCompact(k.active_mrr)} MRR`} />
        <KpiCard label="Net New ARR" value={`${k.net_arr_delta >= 0 ? '+' : ''}${formatGbpCompact(k.net_arr_delta)}`} sub="latest month" status={{ tone: k.net_arr_delta >= 0 ? 'favourable' : 'adverse' }} />
        <KpiCard label="Net Revenue Retention" value={formatPercent(k.nrr)} sub="excl. new business" status={{ tone: nrrTone(k.nrr) }} />
        <KpiCard label="Gross Revenue Retention" value={formatPercent(k.grr)} status={{ tone: k.grr != null && k.grr >= 0.9 ? 'favourable' : 'on-plan' }} />
        <KpiCard label="Logo Retention" value={formatPercent(k.logo_retention)} sub={`${formatCount(k.ending_customers)} customers`} status={{ tone: k.logo_retention != null && k.logo_retention >= 0.9 ? 'favourable' : 'on-plan' }} />
        <KpiCard label="Logo Churn" value={formatPercent(k.logo_churn)} sub={`${formatCount(k.churned_customers)} churned`} status={{ tone: k.logo_churn != null && k.logo_churn <= 0.05 ? 'favourable' : 'neutral' }} />
      </div>

      <div className="panel-grid">
        <ChartCard
          title="SaaS run-rate history"
          subtitle="Full exported history, Jan 2018-Jun 2026: active ARR with NRR overlay"
        >
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={longTrend.data ?? []} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="month_label" stroke={AXIS} fontSize={11} tickLine={false} minTickGap={24} />
              <YAxis yAxisId="money" stroke={AXIS} fontSize={11} tickLine={false} width={56} tickFormatter={(v: number) => formatGbpCompact(v)} />
              <YAxis yAxisId="rate" orientation="right" stroke={AXIS} fontSize={11} tickLine={false} width={44} domain={[0.94, 1.02]} tickFormatter={(v: number) => formatPercent(v, 0)} />
              <Tooltip
                contentStyle={{ background: '#ffffff', border: '1px solid #d6d3cb', borderRadius: 8, color: '#1a1a1a' }}
                formatter={(v: number, name) => [
                  name === 'nrr' ? formatPercent(v) : formatGbp(v),
                  name === 'nrr' ? 'NRR' : 'Active ARR',
                ]}
              />
              <Legend formatter={(v) => (v === 'active_arr' ? 'Active ARR' : 'NRR')} />
              <Line yAxisId="money" type="monotone" dataKey="active_arr" stroke={chart.primary} strokeWidth={2.5} dot={false} />
              <Line yAxisId="rate" type="monotone" dataKey="nrr" stroke={chart.adverse} strokeWidth={1.8} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Retention by segment over time" subtitle="Trailing 36 months: monthly cohort NRR">
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={segmentHistory} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="month_label" stroke={AXIS} fontSize={11} tickLine={false} minTickGap={20} />
              <YAxis stroke={AXIS} fontSize={11} tickLine={false} width={44} domain={[0.94, 1.02]} tickFormatter={(v: number) => formatPercent(v, 0)} />
              <Tooltip
                contentStyle={{ background: '#ffffff', border: '1px solid #d6d3cb', borderRadius: 8, color: '#1a1a1a' }}
                formatter={(v: number, name) => [formatPercent(v), name as string]}
              />
              <Legend />
              {SEGMENTS.map((seg) => (
                <Line key={seg} type="monotone" dataKey={seg} stroke={SEG_FILL[seg]} strokeWidth={2} dot={false} connectNulls />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <ChartCard
        title="Product-family ARR mix"
        subtitle="Trailing 36 months, stacked active ARR by product family"
      >
        <ResponsiveContainer width="100%" height={290}>
          <BarChart data={productHistory} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="month_label" stroke={AXIS} fontSize={11} tickLine={false} minTickGap={20} />
            <YAxis stroke={AXIS} fontSize={11} tickLine={false} width={56} tickFormatter={(v: number) => formatGbpCompact(v)} />
            <Tooltip
              cursor={{ fill: 'rgba(0,0,0,0.03)' }}
              contentStyle={{ background: '#ffffff', border: '1px solid #d6d3cb', borderRadius: 8, color: '#1a1a1a' }}
              formatter={(v: number, name) => [formatGbp(v), name as string]}
            />
            <Legend />
            {Object.keys(PRODUCT_FILL).map((family) => (
              <Bar key={family} dataKey={family} stackId="product" fill={PRODUCT_FILL[family]} radius={family === 'Other' ? [2, 2, 0, 0] : [0, 0, 0, 0]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      {/* FYTD ARR movement bridge */}
      <ChartCard
        title="FYTD ARR movement bridge"
        subtitle="Opening to closing event-led ARR across the SaaS period (GBP) — bars show increase / decrease, not plan variance"
      >
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={walkSteps} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="name" stroke={AXIS} fontSize={11} tickLine={false} />
            <YAxis
              stroke={AXIS}
              fontSize={11}
              tickLine={false}
              width={56}
              tickFormatter={(v: number) => formatGbpCompact(v)}
              domain={[(min: number) => Math.max(0, min - 2_000_000), (max: number) => max + 2_000_000]}
            />
            <Tooltip
              cursor={{ fill: 'rgba(0,0,0,0.03)' }}
              contentStyle={{ background: '#ffffff', border: '1px solid #d6d3cb', borderRadius: 8, color: '#1a1a1a' }}
              formatter={(_v: number, name, props) => {
                if (name === 'base') return [null, null] as unknown as [string, string];
                const step = props.payload as WalkStep;
                return [formatGbp(step.amount), step.name];
              }}
            />
            <Bar dataKey="base" stackId="walk" fill="transparent" />
            <Bar dataKey="value" stackId="walk" radius={[2, 2, 0, 0]}>
              {walkSteps.map((s) => (
                <Cell key={s.name} fill={stepFill(s.kind)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        <p className="pnl-note">
          <strong>Active ARR</strong> ({formatGbp(k.active_arr)}) is the live-subscription run-rate shown in the KPI.
          The bridge uses <strong>event-led ending ARR</strong> ({formatGbp(walk.data.closing)}) for waterfall continuity;
          paused/churned balances are excluded from active ARR, so the two differ slightly by design.
        </p>
      </ChartCard>

      {/* Product & segment depth */}
      <div className="panel-grid" style={{ marginTop: 12 }}>
        <ChartCard title="Active ARR by product & segment" subtitle={`As at ${k.month_label} — stacked by customer segment (GBP)`}>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={prodSegData} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="product_family" stroke={AXIS} fontSize={11} tickLine={false} />
              <YAxis stroke={AXIS} fontSize={11} tickLine={false} width={52} tickFormatter={(v: number) => formatGbpCompact(v)} />
              <Tooltip
                cursor={{ fill: 'rgba(0,0,0,0.03)' }}
                contentStyle={{ background: '#ffffff', border: '1px solid #d6d3cb', borderRadius: 8, color: '#1a1a1a' }}
                formatter={(v: number, name) => [formatGbp(v), name as string]}
              />
              <Legend />
              {SEGMENTS.map((seg) => (
                <Bar key={seg} dataKey={seg} stackId="seg" fill={SEG_FILL[seg]} radius={seg === 'SMB' ? [2, 2, 0, 0] : [0, 0, 0, 0]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="ARR created vs lost by product" subtitle="FYTD gain (new + expansion) vs loss (churn + contraction + pause)">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={prodMove.data ?? []} layout="vertical" margin={{ top: 8, right: 12, left: 8, bottom: 0 }}>
              <CartesianGrid stroke={GRID} horizontal={false} />
              <XAxis type="number" stroke={AXIS} fontSize={11} tickLine={false} tickFormatter={(v: number) => formatGbpCompact(v)} />
              <YAxis type="category" dataKey="product_family" stroke={AXIS} fontSize={11} tickLine={false} width={92} />
              <Tooltip
                cursor={{ fill: 'rgba(0,0,0,0.03)' }}
                contentStyle={{ background: '#ffffff', border: '1px solid #d6d3cb', borderRadius: 8, color: '#1a1a1a' }}
                formatter={(v: number, name) => [formatGbp(Math.abs(v)), name === 'gain' ? 'Gain' : 'Loss']}
              />
              <ReferenceLine x={0} stroke="#d6d3cb" />
              <Bar dataKey="gain" fill={chart.favourable} radius={[0, 2, 2, 0]} />
              <Bar dataKey={(d: { loss: number }) => -d.loss} name="loss" fill={chart.adverse} radius={[2, 0, 0, 2]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* Retention by segment */}
      <div className="panel" style={{ marginTop: 12, paddingBottom: 16 }}>
        <div className="panel-head">
          <div>
            <h3>Retention by segment</h3>
            <p className="panel-sub">FY 2026 monthly cohorts · exposure-weighted NRR/GRR · not a single opening-to-closing FYTD cohort</p>
          </div>
        </div>
        <div className="table-scroll">
        <table className="pnl">
          <thead>
            <tr>
              <th className="row-label">Segment</th>
              <th>Beginning ARR</th>
              <th>NRR</th>
              <th>GRR</th>
              <th>Logo retention</th>
              <th>Churned</th>
              <th className="row-label">Status</th>
            </tr>
          </thead>
          <tbody>
            {(segRet.data ?? []).map((s) => {
              const nrr = s.beginning_arr > 0 ? s.net_retained / s.beginning_arr : null;
              const grr = s.beginning_arr > 0 ? s.gross_retained / s.beginning_arr : null;
              const logo = s.beginning_customers > 0 ? s.retained_customers / s.beginning_customers : null;
              return (
                <tr key={s.customer_segment}>
                  <td className="row-label">{s.customer_segment}</td>
                  <td>{formatGbp(s.beginning_arr)}</td>
                  <td>{formatPercent(nrr)}</td>
                  <td>{formatPercent(grr)}</td>
                  <td>{formatPercent(logo)}</td>
                  <td>{formatCount(s.churned_customers)}</td>
                  <td className="row-label"><StatusPill tone={nrrTone(nrr)} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
        </div>
      </div>

      <div className="panel-grid" style={{ marginTop: 12 }}>
        <ChartCard title="Active ARR by region" subtitle={`As at ${k.month_label} (GBP)`}>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={region.data ?? []} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="region" stroke={AXIS} fontSize={11} tickLine={false} />
              <YAxis stroke={AXIS} fontSize={11} tickLine={false} width={52} tickFormatter={(v: number) => formatGbpCompact(v)} />
              <Tooltip
                cursor={{ fill: 'rgba(0,0,0,0.03)' }}
                contentStyle={{ background: '#ffffff', border: '1px solid #d6d3cb', borderRadius: 8, color: '#1a1a1a' }}
                formatter={(v: number, _n, props) => [`${formatGbp(v)} · NRR ${formatPercent((props.payload as { nrr: number | null }).nrr)}`, 'Active ARR']}
              />
              <Bar dataKey="active_arr" fill={chart.primary} radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Retention trend" subtitle="NRR vs GRR (%)">
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={trend.data ?? []} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="month_label" stroke={AXIS} fontSize={11} tickLine={false} />
              <YAxis stroke={AXIS} fontSize={11} tickLine={false} width={48} domain={[0.9, 1.05]} tickFormatter={(v: number) => formatPercent(v, 0)} />
              <Tooltip
                contentStyle={{ background: '#ffffff', border: '1px solid #d6d3cb', borderRadius: 8, color: '#1a1a1a' }}
                formatter={(v: number, name) => [formatPercent(v), name === 'nrr' ? 'NRR' : 'GRR']}
              />
              <Legend formatter={(v) => (v === 'nrr' ? 'NRR' : 'GRR')} />
              <Line type="monotone" dataKey="nrr" stroke={chart.primary} strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="grr" stroke={chart.secondary} strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <div className="tile-grid">
        <div className="tile tone-favourable">
          <div className="tile-title">New customers</div>
          <div className="tile-primary">{formatCount(k.new_customers)}</div>
          <div className="tile-primary-label">acquired ({k.month_label})</div>
        </div>
        <div className="tile tone-on-plan">
          <div className="tile-title">Retained customers</div>
          <div className="tile-primary">{formatCount(k.retained_customers)}</div>
          <div className="tile-primary-label">of {formatCount(k.beginning_customers)} opening</div>
        </div>
        <div className="tile tone-adverse">
          <div className="tile-title">Churned customers</div>
          <div className="tile-primary">{formatCount(k.churned_customers)}</div>
          <div className="tile-primary-label">logo churn {formatPercent(k.logo_churn)}</div>
        </div>
        <div className="tile tone-neutral">
          <div className="tile-title">Paused customers</div>
          <div className="tile-primary">{formatCount(k.paused_customers)}</div>
          <div className="tile-primary-label">{formatCount(k.active_subscriptions)} active subs</div>
        </div>
      </div>

      <div className="narrative">
        <h3>SaaS commentary</h3>
        <p>{narrative}</p>
      </div>
    </>
  );
}
