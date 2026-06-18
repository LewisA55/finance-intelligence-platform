import type { CommandCenterKpis } from '../types';
import { formatGbp } from '../lib/format';

interface PnlSummaryProps {
  kpis: CommandCenterKpis;
}

interface PnlRow {
  label: string;
  actual: number;
  budget: number;
  forecast: number;
  higherIsBetter: boolean;
  total?: boolean;
}

function varianceCell(row: PnlRow, hasActuals: boolean) {
  if (!hasActuals) return { text: '—', cls: '' };
  const v = row.actual - row.budget;
  const favourable = row.higherIsBetter ? v >= 0 : v <= 0;
  const sign = v > 0 ? '+' : '';
  return { text: `${sign}${formatGbp(v)}`, cls: favourable ? 'fav' : 'adv' };
}

/**
 * Operating-basis P&L summary built only from fields present on the executive
 * mart (revenue, operating expense, operating result). No COGS split exists in
 * the mart, so gross margin is intentionally not shown (see note).
 */
export function PnlSummary({ kpis }: PnlSummaryProps) {
  const hasActuals = kpis.actual_revenue > 0;

  const rows: PnlRow[] = [
    {
      label: 'Revenue',
      actual: kpis.actual_revenue,
      budget: kpis.budget_revenue,
      forecast: kpis.forecast_revenue,
      higherIsBetter: true,
    },
    {
      label: 'Operating expenses',
      actual: kpis.actual_expense,
      budget: kpis.budget_expense,
      forecast: kpis.forecast_expense,
      higherIsBetter: false,
    },
    {
      label: 'Operating result',
      actual: kpis.operating_result,
      budget: kpis.budget_operating_result,
      forecast: kpis.forecast_operating_result,
      higherIsBetter: true,
      total: true,
    },
  ];

  return (
    <div className="panel" style={{ paddingBottom: 16 }}>
      <div className="panel-head">
        <div>
          <h3>P&amp;L summary</h3>
          <p className="panel-sub">Operating basis · {kpis.month_label} · GBP · Company Total</p>
        </div>
      </div>
      <div className="table-scroll">
      <table className="pnl">
        <thead>
          <tr>
            <th className="row-label">Line</th>
            <th>Actual</th>
            <th>Budget</th>
            <th>Forecast</th>
            <th>Var vs budget</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const v = varianceCell(row, hasActuals);
            return (
              <tr key={row.label} className={row.total ? 'total' : ''}>
                <td className="row-label">{row.label}</td>
                <td>{hasActuals ? formatGbp(row.actual) : '—'}</td>
                <td>{formatGbp(row.budget)}</td>
                <td>{formatGbp(row.forecast)}</td>
                <td className={v.cls}>{v.text}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      </div>
      <p className="pnl-note">
        Operating basis — gross margin is intentionally omitted as the executive mart
        carries total operating expense, not a COGS split.{' '}
        {!hasActuals && 'Actuals are not yet recognised for this period (plan-only).'}
      </p>
    </div>
  );
}
