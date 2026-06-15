import { useQuery } from '../hooks/useQuery';
import { getDataAsAt } from '../duckdb/queries';

function monthUpper(iso: string | null): string {
  if (!iso) return '—';
  return new Date(`${iso}T00:00:00`)
    .toLocaleDateString('en-GB', { month: 'short', year: 'numeric' })
    .toUpperCase();
}

function dayUpper(iso: string | null): string {
  if (!iso) return '—';
  return new Date(`${iso}T00:00:00`)
    .toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
    .toUpperCase();
}

/**
 * Management-pack cover header: entity + pack identity on the left, live
 * provenance metadata on the right. All metadata is read from the mart itself
 * (build date, as-of actuals month) — nothing is hardcoded.
 */
export function PackHeader() {
  const { data } = useQuery(getDataAsAt, []);

  return (
    <header className="pack-header">
      <div className="pack-title">
        <h1>Atlas — Nexus Technologies</h1>
        <div className="pack-sub">FY 2026 · Internal · Synthetic demo · CFO Intelligence Pack</div>
      </div>
      <div className="pack-meta">
        <span className="live">LIVE</span> · BUILT {dayUpper(data?.built_date ?? null)}
        <br />
        AS OF {monthUpper(data?.latest_actuals_month ?? null)} · COMPANY TOTAL
      </div>
    </header>
  );
}
