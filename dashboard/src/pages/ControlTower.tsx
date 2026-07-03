import { useMemo } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { useQuery } from '../hooks/useQuery';
import { getControlSummary, getControlHistory, getModelReadinessControls } from '../duckdb/queries';
import { TopBar } from '../components/TopBar';
import { KpiCard } from '../components/KpiCard';
import { ChartCard } from '../components/ChartCard';
import { StatusPill, type StatusTone } from '../components/StatusPill';
import { formatCount } from '../lib/format';
import { chart } from '../lib/theme';
import type { PageId } from '../nav';
import type { ModelReadinessControl } from '../types';

// Locked warehouse milestone from docs/final_validation_summary.md. These are
// release evidence, not live test results from the browser session.
const DBT = {
  tableModels: 37,
  viewModels: 30,
  dataTests: 2946,
  milestone: 'v1.0-dbt-warehouse-complete',
};

const TREATMENT_RANK: Record<string, number> = {
  'Model Blocking': 0,
  'Usable with review': 1,
  'Accepted Limitation': 2,
  Monitor: 3,
};

function treatmentTone(treatment: string): StatusTone {
  if (treatment === 'Model Blocking') return 'adverse';
  if (treatment === 'Usable with review') return 'warning';
  return 'neutral';
}

/** Short display language: Blocking / Review / Accepted / Monitor. */
function treatmentLabel(treatment: string): string {
  if (treatment === 'Model Blocking') return 'Blocking';
  if (treatment === 'Usable with review') return 'Review';
  if (treatment === 'Accepted Limitation') return 'Accepted';
  return treatment;
}

/** Worst (most restrictive) readiness treatment among a domain's policy controls. */
function worstControl(controls: ModelReadinessControl[]): ModelReadinessControl | null {
  return controls.reduce<ModelReadinessControl | null>(
    (worst, c) =>
      !worst || (TREATMENT_RANK[c.treatment] ?? 9) < (TREATMENT_RANK[worst.treatment] ?? 9) ? c : worst,
    null,
  );
}

export function ControlTower({ onNavigate }: { onNavigate: (page: PageId) => void }) {
  const { data: c, loading, error } = useQuery(getControlSummary, []);
  const history = useQuery(getControlHistory, []);
  const policy = useQuery(getModelReadinessControls, []);

  const historyData = useMemo(() => {
    const byMonth = new Map<string, Record<string, number | string>>();
    for (const row of history.data ?? []) {
      const current = byMonth.get(row.month_iso) ?? { month_iso: row.month_iso, month_label: row.month_label };
      current[row.domain] = row.exception_count;
      byMonth.set(row.month_iso, current);
    }
    return Array.from(byMonth.values()).sort((a, b) => String(a.month_iso).localeCompare(String(b.month_iso)));
  }, [history.data]);

  // Raw exception counts are incomparable across domains; give each a
  // denominator: months affected out of months tracked.
  const domainRates = useMemo(() => {
    const rates = new Map<string, { affected: number; tracked: number }>();
    for (const row of history.data ?? []) {
      // The register aggregates both SaaS histories into one domain row.
      const key = row.domain.startsWith('SaaS') ? 'SaaS' : row.domain;
      const entry = rates.get(key) ?? { affected: 0, tracked: 0 };
      entry.tracked += 1;
      if (row.exception_count > 0) entry.affected += 1;
      rates.set(key, entry);
    }
    return rates;
  }, [history.data]);

  const domainColours: Record<string, string> = {
    'Financial Performance': chart.primary,
    'Order-to-Cash': chart.secondary,
    'Revenue Recognition': chart.budget,
    'Deferred Revenue': chart.amber,
    'Accounts Payable': chart.adverse,
    Workforce: chart.favourable,
    'SaaS ARR': '#6b7280',
    'SaaS Retention': '#374151',
  };

  if (loading) {
    return (
      <div className="state">
        <div className="spinner" />
        <div>Loading control telemetry…</div>
      </div>
    );
  }
  if (error || history.error || policy.error) {
    return <div className="error-box"><strong>Could not load data.</strong><div>{(error || history.error || policy.error)?.message}</div></div>;
  }
  if (!c) return <div className="state">No control data.</div>;

  const policyByDomain = (domain: string) =>
    (policy.data ?? []).filter((p) => p.control_domain === domain || (domain === 'SaaS' && p.control_domain.startsWith('SaaS')));

  const domains = [
    { name: 'Financial Performance', flag: c.financial_flag, exceptions: c.financial_exceptions, source: 'mart_financial_performance', page: 'financial' as PageId },
    { name: 'Order-to-Cash', flag: c.o2c_flag, exceptions: c.o2c_exceptions, source: 'mart_o2c_customer_collections', page: 'working-capital' as PageId },
    { name: 'Revenue Recognition', flag: c.revenue_flag, exceptions: c.revenue_exceptions, source: 'mart_revenue_waterfall', page: 'revenue' as PageId },
    { name: 'Deferred Revenue', flag: c.deferred_flag, exceptions: c.deferred_exceptions, source: 'mart_deferred_revenue_control', page: 'revenue' as PageId },
    { name: 'Accounts Payable', flag: c.ap_flag, exceptions: c.ap_exceptions, source: 'mart_ap_working_capital_control', page: 'working-capital' as PageId },
    { name: 'Workforce', flag: c.workforce_flag, exceptions: c.workforce_exceptions, source: 'mart_workforce_cost_control', page: 'workforce' as PageId },
    { name: 'SaaS', flag: c.saas_flag, exceptions: c.saas_exceptions, source: 'mart_saas_arr_movement · retention', page: 'saas' as PageId },
  ]
    .map((d) => {
      const worst = d.flag ? worstControl(policyByDomain(d.name)) : null;
      return { ...d, worst };
    })
    // Severity grouping: blocking first, clean last.
    .sort((a, b) => {
      const rank = (d: { flag: boolean; worst: ModelReadinessControl | null }) =>
        !d.flag ? 9 : TREATMENT_RANK[d.worst?.treatment ?? ''] ?? 8;
      return rank(a) - rank(b);
    });

  const flagged = domains.filter((d) => d.flag);
  const blockingCount = flagged.filter((d) => d.worst?.treatment === 'Model Blocking').length;
  const reviewCount = flagged.filter((d) => d.worst?.treatment === 'Usable with review').length;
  const acceptedCount = flagged.filter(
    (d) => d.worst && (d.worst.treatment === 'Accepted Limitation' || d.worst.treatment === 'Monitor'),
  ).length;

  return (
    <>
      <TopBar
        title="Control Tower"
        subtitle="Which numbers can be trusted — and what does each control mean for model use?"
        actions={<span className="scope-pill">Scope: Company Total</span>}
      />

      {/* Overall trust verdict */}
      <div className={`trustbar ${c.any_flag ? 'warn' : 'ok'}`}>
        <div className="tb-icon">{c.any_flag ? '⚠' : '✓'}</div>
        <div className="tb-body">
          <div className="tb-head">Trust verdict · FY 2026 reporting snapshot</div>
          <div className="tb-text">
            {c.any_flag ? (
              <>
                <strong>Safe to use — with review.</strong> {flagged.length} of {domains.length} domains
                carry observations under the model-readiness policy: {formatCount(blockingCount)} model-blocking,{' '}
                {formatCount(reviewCount)} usable with review, {formatCount(acceptedCount)} accepted
                limitations or monitoring signals. Exceptions are surfaced, not hidden; figures remain
                governed Company-Total.
              </>
            ) : (
              <>
                <strong>Safe to use.</strong> No control exceptions across any domain for the
                {' '}{c.months} reporting months.
              </>
            )}
          </div>
        </div>
      </div>

      {/* Readiness cockpit: domains by treatment, not raw exception counts */}
      <div className="tile-grid" style={{ marginBottom: 20 }}>
        <div className={`tile ${blockingCount > 0 ? 'tone-adverse' : 'tone-favourable'}`}>
          <div className="tile-title">Blocking</div>
          <div className="tile-primary">{formatCount(blockingCount)}</div>
          <div className="tile-primary-label">domains stop the CFO model</div>
          <div className="tile-secondary">{blockingCount > 0 ? 'Clear before model sign-off' : 'Nothing blocks the model'}</div>
        </div>
        <div className={`tile ${reviewCount > 0 ? 'tone-on-plan' : 'tone-favourable'}`}>
          <div className="tile-title">Review</div>
          <div className="tile-primary">{formatCount(reviewCount)}</div>
          <div className="tile-primary-label">usable with review</div>
          <div className="tile-secondary">Disclose and review before reliance</div>
        </div>
        <div className="tile tone-neutral">
          <div className="tile-title">Accepted / Monitor</div>
          <div className="tile-primary">{formatCount(acceptedCount)}</div>
          <div className="tile-primary-label">disclosed limitations</div>
          <div className="tile-secondary">Known behaviour, not failures</div>
        </div>
        <div className="tile tone-favourable">
          <div className="tile-title">Clean</div>
          <div className="tile-primary">{formatCount(domains.length - flagged.length)}</div>
          <div className="tile-primary-label">domains without observations</div>
          <div className="tile-secondary">Usable without caveats</div>
        </div>
      </div>

      {/* Validation evidence */}
      <div className="kpi-grid">
          <KpiCard label="Table models" value={formatCount(DBT.tableModels)} sub="locked dbt milestone" />
          <KpiCard label="View models" value={formatCount(DBT.viewModels)} sub="locked dbt milestone" />
          <KpiCard label="Data tests" value={formatCount(DBT.dataTests)} sub={DBT.milestone} />
        <KpiCard
          label="Test failures"
          value="0"
          sub="0 warnings · 0 skips"
          status={{ tone: 'favourable', label: 'Pass' }}
        />
      </div>

      <ChartCard
        title="Control exception history"
        subtitle="All available domain histories: SaaS 2018-2026, O2C/AP 2023-2026, revenue 2022-2027, workforce 2022-2027"
      >
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={historyData} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
            <CartesianGrid stroke={chart.grid} vertical={false} />
            <XAxis dataKey="month_label" stroke={chart.axis} fontSize={11} tickLine={false} minTickGap={24} />
            <YAxis stroke={chart.axis} fontSize={11} tickLine={false} width={44} tickFormatter={(v: number) => formatCount(v)} />
            <Tooltip
              cursor={{ fill: 'rgba(0,0,0,0.03)' }}
              contentStyle={{ background: '#ffffff', border: '1px solid #d6d3cb', borderRadius: 8, color: '#1a1a1a' }}
              formatter={(v: number, name) => [formatCount(v), name as string]}
            />
            <Legend />
            {Object.entries(domainColours).map(([domain, fill]) => (
              <Bar key={domain} dataKey={domain} stackId="domain" fill={fill} radius={[0, 0, 0, 0]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      {/* Domain control register */}
      <div className="panel" style={{ paddingBottom: 16 }}>
        <div className="panel-head">
          <div>
            <h3>Domain control register</h3>
            <p className="panel-sub">Observations classified by model-readiness treatment — accepted limitations are disclosed, not failures</p>
          </div>
        </div>
        <div className="table-scroll">
        <table className="pnl model-policy-table">
          <thead>
            <tr>
              <th className="row-label">Domain</th>
              <th className="row-label">Treatment</th>
              <th>Observations</th>
              <th>Months affected</th>
              <th className="row-label">What this means for model use</th>
              <th className="row-label">Drill into</th>
            </tr>
          </thead>
          <tbody>
            {domains.map((d) => (
              <tr key={d.name}>
                <td className="row-label">
                  {d.name}
                  <div className="tile-source"><code>{d.source}</code></div>
                </td>
                <td className="row-label">
                  <StatusPill
                    tone={d.flag ? (d.worst ? treatmentTone(d.worst.treatment) : 'warning') : 'favourable'}
                    label={d.flag ? treatmentLabel(d.worst?.treatment ?? 'Review') : 'Clean'}
                  />
                </td>
                <td className={d.flag && d.worst?.treatment === 'Model Blocking' ? 'adv' : ''}>{formatCount(d.exceptions)}</td>
                <td>
                  {(() => {
                    const rate = domainRates.get(d.name);
                    if (!rate || rate.tracked === 0) return '—';
                    return `${formatCount(rate.affected)} of ${formatCount(rate.tracked)} (${Math.round((rate.affected / rate.tracked) * 100)}%)`;
                  })()}
                </td>
                <td className="row-label">
                  {d.flag
                    ? d.worst?.recommended_treatment ?? 'Review the observations before relying on this domain.'
                    : 'No observations — usable without caveats.'}
                </td>
                <td className="row-label">
                  <button type="button" className="drillthrough-link" onClick={() => onNavigate(d.page)}>
                    {d.page === 'working-capital' ? 'Working Capital' : d.page === 'revenue' ? 'Revenue' : d.page.charAt(0).toUpperCase() + d.page.slice(1)} →
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>

      <div className="narrative">
        <h3>Why this is credible</h3>
        <p>
          Project Atlas is built control-first: synthetic source systems carry deliberate
          defects, the dbt layer enforces {formatCount(DBT.dataTests)} data tests across{' '}
          {DBT.tableModels + DBT.viewModels} models, and the governed marts retain control
          telemetry rather than masking it. Observations are classified under the
          model-readiness policy — model-blocking issues stop the CFO model, accepted
          limitations are disclosed and worked around, monitoring signals are tracked — so a
          reviewer can see exactly what each domain means for downstream use before any number
          is relied upon.
        </p>
      </div>
    </>
  );
}
