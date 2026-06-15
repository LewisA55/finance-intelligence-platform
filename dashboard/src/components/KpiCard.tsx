import { StatusPill, type StatusTone } from './StatusPill';

interface KpiCardProps {
  label: string;
  value: string;
  /** Secondary line, e.g. "vs £6.8M budget". */
  sub?: string;
  /** Variance / movement indicator. */
  delta?: { text: string; direction: 'up' | 'down' | 'flat' };
  /** Favourable / Adverse / On Plan pill. */
  status?: { tone: StatusTone; label?: string };
}

export function KpiCard({ label, value, sub, delta, status }: KpiCardProps) {
  return (
    <div className="kpi">
      <div className="kpi-top">
        <span className="label">{label}</span>
        {status && <StatusPill tone={status.tone} label={status.label} />}
      </div>
      <div className="value">{value}</div>
      {(delta || sub) && (
        <div className="sub">
          {delta && (
            <span className={`delta ${delta.direction}`}>
              {delta.direction === 'up' ? '▲' : delta.direction === 'down' ? '▼' : '■'}{' '}
              {delta.text}
            </span>
          )}
          {sub && <span>{sub}</span>}
        </div>
      )}
    </div>
  );
}
