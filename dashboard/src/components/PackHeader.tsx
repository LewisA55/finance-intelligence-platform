import { useQuery } from '../hooks/useQuery';
import { getDataAsAt, getSnapshotManifest, getModelReadinessSummary } from '../duckdb/queries';

function monthUpper(iso: string | null): string {
  if (!iso) return '—';
  return new Date(`${iso}T00:00:00`)
    .toLocaleDateString('en-GB', { month: 'short', year: 'numeric' })
    .toUpperCase();
}

function dayUpper(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso.includes('T') ? iso : `${iso}T00:00:00`)
    .toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
    .toUpperCase();
}

/**
 * Management-pack cover header: entity + pack identity on the left, live
 * provenance metadata on the right. The three as-of dates deliberately differ
 * and are labelled explicitly: finance close (executive mart actuals),
 * operational actuals (model-serving feed), and model import-ready months.
 * All metadata is read from the shipped data itself — nothing is hardcoded.
 */
export function PackHeader() {
  const { data, error } = useQuery(getDataAsAt, []);
  const manifest = useQuery(getSnapshotManifest, []);
  const readiness = useQuery(getModelReadinessSummary, []);

  return (
    <header className="pack-header">
      <div className="pack-title">
        <h1>Atlas — Nexus Technologies</h1>
        <div className="pack-sub">FY 2026 · Internal · Synthetic demo · CFO Intelligence Pack</div>
      </div>
      <div className="pack-meta" data-provenance-error={error?.message}>
        <span className="live">LIVE</span> · SNAPSHOT {dayUpper(manifest.data?.generatedAt ?? null)} · WAREHOUSE {dayUpper(data?.built_date ?? null)}
        <br />
        FINANCE CLOSE {monthUpper(data?.latest_actuals_month ?? null)} · OPS ACTUALS TO {(readiness.data?.latest_actual_month_label ?? '—').toUpperCase()}
        <br />
        MODEL-READY TO {(readiness.data?.latest_excel_month_label ?? '—').toUpperCase()} · COMPANY TOTAL
      </div>
    </header>
  );
}
