import { useQuery } from '../hooks/useQuery';
import {
  getSnapshotManifest,
  getValidationInfo,
  getModelReadinessSummary,
  getModelReadinessControls,
  getTableEvidence,
  getMetricReadiness,
} from '../duckdb/queries';
import { TopBar } from '../components/TopBar';
import { StatusPill } from '../components/StatusPill';
import { formatCount } from '../lib/format';

function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${bytes} B`;
}

export function Validation() {
  const { data, loading, error } = useQuery(getValidationInfo, []);
  const manifest = useQuery(getSnapshotManifest, []);
  const readiness = useQuery(getModelReadinessSummary, []);
  const controls = useQuery(getModelReadinessControls, []);
  const evidence = useQuery(getTableEvidence, []);
  const metricReadiness = useQuery(getMetricReadiness, []);
  const anyError =
    error || manifest.error || readiness.error || controls.error || evidence.error || metricReadiness.error;

  const manifestByName = new Map(
    (manifest.data?.files ?? []).map((f) => [f.name.replace(/\.(parquet|csv)$/, ''), f]),
  );
  const r = readiness.data ?? null;

  return (
    <>
      <TopBar
        title="Data & Validation"
        subtitle="What exactly shipped in this snapshot — and is it fresh, complete and hash-verified?"
      />

      {loading && (
        <div className="state">
          <div className="spinner" />
          <div>Running validation queries…</div>
        </div>
      )}
      {anyError && <div className="error-box">{anyError.message}</div>}

      {data && (
        <>
          <div className="validation-grid">
            {manifest.data && (
              <div className="panel">
                <h3>Snapshot contract</h3>
                <p className="panel-sub">Hash-validated files shipped with this dashboard build</p>
                <ul className="kv">
                  <li><span>Manifest schema</span><strong>v{manifest.data.schemaVersion}</strong></li>
                  <li><span>Files</span><strong>{formatCount(manifest.data.files.length)}</strong></li>
                  <li>
                    <span>Payload</span>
                    <strong>{formatBytes(manifest.data.files.reduce((sum, f) => sum + f.bytes, 0))}</strong>
                  </li>
                  <li><span>Generated</span><strong>{new Date(manifest.data.generatedAt).toLocaleDateString('en-GB')}</strong></li>
                  <li><span>Source commit</span><strong><code>{manifest.data.gitCommit.slice(0, 8)}</code></strong></li>
                </ul>
              </div>
            )}

            <div className="panel">
              <h3>Model-serving readiness</h3>
              <p className="panel-sub">The contract consumed by the Excel model and the Forecast &amp; Valuation page</p>
              <ul className="kv">
                <li>
                  <span>Actuals feed</span>
                  <strong>
                    {r ? `${formatCount(r.excel_actual_months)} import-ready months` : '—'}
                  </strong>
                </li>
                <li><span>Latest actual month</span><strong>{r?.latest_actual_month_label ?? '—'}</strong></li>
                <li><span>Latest scheduled month</span><strong>{r?.latest_scheduled_month_label ?? '—'}</strong></li>
                <li>
                  <span>Opening balance sheet</span>
                  <strong>
                    {r ? (
                      <StatusPill tone={r.opening_bs_balanced ? 'favourable' : 'adverse'} label={r.opening_bs_balanced ? 'Balanced' : 'Check'} />
                    ) : '—'}
                  </strong>
                </li>
                <li>
                  <span>Readiness controls</span>
                  <strong>{controls.data ? `${formatCount(controls.data.length)} classified` : '—'}</strong>
                </li>
                <li>
                  <span>Blocked periods</span>
                  <strong>{r ? formatCount(r.blocked_months) : '—'}</strong>
                </li>
              </ul>
            </div>

            <div className="panel">
              <h3>Executive mart</h3>
              <ul className="kv">
                <li><span>Total rows</span><strong>{formatCount(data.execMartRowCount)}</strong></li>
                <li><span>Company-Total rows</span><strong>{formatCount(data.companyTotalRowCount)}</strong></li>
                <li><span>Latest reporting month</span><strong>{data.latestReportingMonth}</strong></li>
                <li><span>Latest actuals month</span><strong>{data.latestActualsMonth ?? '—'}</strong></li>
              </ul>
            </div>

            <div className="panel">
              <h3>Reporting scopes</h3>
              <p className="panel-sub">Scopes are never aggregated together (fan-out guard)</p>
              <ul className="kv">
                {data.scopeCounts.map((s) => (
                  <li key={s.reporting_scope}>
                    <span>{s.reporting_scope}</span>
                    <strong>{formatCount(s.rows)}</strong>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="panel" style={{ marginTop: 12, paddingBottom: 16 }}>
            <div className="panel-head">
              <div>
                <h3>Metric presentation readiness</h3>
                <p className="panel-sub">
                  Per-metric registry from <code>mart_cfo_metric_readiness</code>: signal coverage,
                  exclusions and the presentation policy each metric sits under
                </p>
              </div>
            </div>
            <div className="table-scroll">
              <table className="pnl">
                <thead>
                  <tr>
                    <th className="row-label">Metric</th>
                    <th>Unit</th>
                    <th className="row-label">Signal coverage</th>
                    <th>Presented</th>
                    <th>Excluded</th>
                    <th className="row-label">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {(metricReadiness.data ?? []).map((m) => (
                    <tr key={m.metric_code}>
                      <td className="row-label">{m.metric_name}</td>
                      <td>{m.unit}</td>
                      <td className="row-label">
                        {m.coverage_from ? `${m.coverage_from} → ${m.coverage_to}` : '—'}
                      </td>
                      <td>{formatCount(m.months_presented)} of {formatCount(m.months_total)}</td>
                      <td className={m.months_excluded > 0 ? 'adv' : ''}>{formatCount(m.months_excluded)}</td>
                      <td className="row-label">
                        <StatusPill
                          tone={
                            m.presentation_basis_status === 'Presented'
                              ? 'favourable'
                              : m.presentation_basis_status === 'Presented with exclusions'
                                ? 'warning'
                                : 'neutral'
                          }
                          label={m.presentation_basis_status.replace('Presented with ', '+ ')}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="pnl-note">
              Presented values differ from as-found values only under the committed presentation
              policy (<code>presentation_policy</code> seed) — every adjustment is disclosed.
            </p>
          </div>

          <div className="panel" style={{ marginTop: 12, paddingBottom: 16 }}>
            <div className="panel-head">
              <div>
                <h3>Data evidence</h3>
                <p className="panel-sub">Every registered table: rows, coverage window, source and shipped size</p>
              </div>
            </div>
            <div className="table-scroll">
              <table className="pnl">
                <thead>
                  <tr>
                    <th className="row-label">Table</th>
                    <th>Rows</th>
                    <th className="row-label">Coverage</th>
                    <th>Source</th>
                    <th>Size</th>
                  </tr>
                </thead>
                <tbody>
                  {(evidence.data ?? []).map((t) => {
                    const file = manifestByName.get(t.table_name);
                    return (
                      <tr key={t.table_name}>
                        <td className="row-label"><code>{t.table_name}</code></td>
                        <td>{formatCount(t.rows)}</td>
                        <td className="row-label">
                          {t.from_date ? `${t.from_date} → ${t.to_date}` : 'reference / snapshot'}
                        </td>
                        <td>{file?.source ?? '—'}</td>
                        <td>{file ? formatBytes(file.bytes) : '—'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {!evidence.data && !anyError && <p className="pnl-note">Profiling registered tables…</p>}
          </div>
        </>
      )}
    </>
  );
}
