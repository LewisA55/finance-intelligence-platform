import { useQuery } from '../hooks/useQuery';
import { getSnapshotManifest, getValidationInfo } from '../duckdb/queries';
import { TopBar } from '../components/TopBar';
import { formatCount } from '../lib/format';

export function Validation() {
  const { data, loading, error } = useQuery(getValidationInfo, []);
  const manifest = useQuery(getSnapshotManifest, []);
  const anyError = error || manifest.error;

  return (
    <>
      <TopBar
        title="Data & Validation"
        subtitle="Auditable provenance for every figure shown in the app"
      />

      {loading && (
        <div className="state">
          <div className="spinner" />
          <div>Running validation queries…</div>
        </div>
      )}
      {anyError && <div className="error-box">{anyError.message}</div>}

      {data && (
        <div className="validation-grid">
          <div className="panel">
            <h3>Loaded tables</h3>
            <p className="panel-sub">Registered as DuckDB-WASM views from Parquet</p>
            <ul className="kv">
              {data.tables.map((t) => (
                <li key={t}><code>{t}</code></li>
              ))}
            </ul>
          </div>

          {manifest.data && (
            <div className="panel">
              <h3>Snapshot contract</h3>
              <p className="panel-sub">Hash-validated files shipped with this dashboard build</p>
              <ul className="kv">
                <li><span>Manifest schema</span><strong>v{manifest.data.schemaVersion}</strong></li>
                <li><span>Files</span><strong>{formatCount(manifest.data.files.length)}</strong></li>
                <li><span>Generated</span><strong>{new Date(manifest.data.generatedAt).toLocaleDateString('en-GB')}</strong></li>
                <li><span>Source commit</span><strong><code>{manifest.data.gitCommit.slice(0, 8)}</code></strong></li>
              </ul>
            </div>
          )}

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
      )}
    </>
  );
}
