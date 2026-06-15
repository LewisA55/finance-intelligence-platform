import { useQuery } from '../hooks/useQuery';
import { getControlSummary } from '../duckdb/queries';
import { TopBar } from '../components/TopBar';
import { KpiCard } from '../components/KpiCard';
import { StatusPill } from '../components/StatusPill';
import { formatCount } from '../lib/format';

// Mirrors the locked dbt warehouse milestone (docs/final_validation_summary.md).
// These are the validation evidence behind every governed figure in the pack.
const DBT = { tableModels: 37, viewModels: 30, dataTests: 2946 };

export function ControlTower() {
  const { data: c, loading, error } = useQuery(getControlSummary, []);

  if (loading) {
    return (
      <div className="state">
        <div className="spinner" />
        <div>Loading control telemetry…</div>
      </div>
    );
  }
  if (error) return <div className="error-box"><strong>Could not load data.</strong><div>{error.message}</div></div>;
  if (!c) return <div className="state">No control data.</div>;

  const domains = [
    { name: 'Financial Performance', flag: c.financial_flag, exceptions: c.financial_exceptions, source: 'mart_financial_performance' },
    { name: 'Order-to-Cash', flag: c.o2c_flag, exceptions: c.o2c_exceptions, source: 'mart_o2c_customer_collections' },
    { name: 'Revenue Recognition', flag: c.revenue_flag, exceptions: c.revenue_exceptions, source: 'mart_revenue_waterfall' },
    { name: 'Deferred Revenue', flag: c.deferred_flag, exceptions: c.deferred_exceptions, source: 'mart_deferred_revenue_control' },
    { name: 'Accounts Payable', flag: c.ap_flag, exceptions: c.ap_exceptions, source: 'mart_ap_working_capital_control' },
    { name: 'Workforce', flag: c.workforce_flag, exceptions: c.workforce_exceptions, source: 'mart_workforce_cost_control' },
    { name: 'SaaS', flag: c.saas_flag, exceptions: c.saas_exceptions, source: 'mart_saas_arr_movement · retention' },
  ];

  const flagged = domains.filter((d) => d.flag).length;

  return (
    <>
      <TopBar
        title="Control Tower"
        subtitle="Governed control exceptions & validation evidence — why this pack is trustworthy"
        actions={<span className="scope-pill">Scope: Company Total</span>}
      />

      {/* Overall trust verdict */}
      <div className={`trustbar ${c.any_flag ? 'warn' : 'ok'}`}>
        <div className="tb-icon">{c.any_flag ? '⚠' : '✓'}</div>
        <div className="tb-body">
          <div className="tb-head">Trust verdict · FY 2026 to date</div>
          <div className="tb-text">
            {c.any_flag ? (
              <>
                <strong>Safe to use — with review.</strong> {flagged} of {domains.length} domains
                carry control exceptions across {c.months} reporting months. Exceptions are
                surfaced, not hidden; figures remain governed Company-Total.
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

      {/* Validation evidence */}
      <div className="kpi-grid">
        <KpiCard label="Table models" value={formatCount(DBT.tableModels)} sub="dbt gold layer" />
        <KpiCard label="View models" value={formatCount(DBT.viewModels)} sub="dbt silver layer" />
        <KpiCard label="Data tests" value={formatCount(DBT.dataTests)} sub="governed assertions" />
        <KpiCard
          label="Test failures"
          value="0"
          sub="0 warnings · 0 skips"
          status={{ tone: 'favourable', label: 'Pass' }}
        />
      </div>

      {/* Domain control register */}
      <div className="panel" style={{ paddingBottom: 16 }}>
        <div className="panel-head">
          <div>
            <h3>Domain control register</h3>
            <p className="panel-sub">Control exceptions by domain across FY 2026 to date</p>
          </div>
        </div>
        <table className="pnl">
          <thead>
            <tr>
              <th className="row-label">Domain</th>
              <th className="row-label">Control status</th>
              <th>Exceptions</th>
              <th className="row-label">Governing mart</th>
            </tr>
          </thead>
          <tbody>
            {domains.map((d) => (
              <tr key={d.name}>
                <td className="row-label">{d.name}</td>
                <td className="row-label">
                  <StatusPill
                    tone={d.flag ? 'warning' : 'favourable'}
                    label={d.flag ? 'Needs review' : 'Clean'}
                  />
                </td>
                <td className={d.flag ? 'adv' : ''}>{formatCount(d.exceptions)}</td>
                <td className="row-label"><code>{d.source}</code></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="narrative">
        <h3>Why this is credible</h3>
        <p>
          Project Atlas is built control-first: synthetic source systems carry deliberate
          defects, the dbt layer enforces {formatCount(DBT.dataTests)} data tests across{' '}
          {DBT.tableModels + DBT.viewModels} models, and the governed marts retain control
          telemetry rather than masking it. This page reads that telemetry straight from the
          executive mart, so a reviewer can see exactly which domains are clean and which
          warrant review before any number is relied upon.
        </p>
      </div>
    </>
  );
}
