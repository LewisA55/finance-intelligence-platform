import { useEffect, useMemo, useState } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
} from 'recharts';
import { useQuery } from '../hooks/useQuery';
import { getWorkforceDepartments, getWorkforceTrend } from '../duckdb/queries';
import { TopBar } from '../components/TopBar';
import { KpiCard } from '../components/KpiCard';
import { ChartCard } from '../components/ChartCard';
import { StatusPill, type StatusTone } from '../components/StatusPill';
import { chart } from '../lib/theme';
import { formatCount, formatGbp, formatGbpCompact } from '../lib/format';

const GRID = chart.grid;
const AXIS = chart.axis;

const COST_SERIES_LABELS: Record<string, string> = {
  payroll_actual: 'Payroll (actual)',
  payroll_plan: 'Payroll (plan)',
  fte_actual: 'FTE (actual)',
  fte_plan: 'FTE (plan)',
};

/**
 * Workforce observations are never model-blocking under the model-readiness
 * policy: ghost records are a disclosed accepted limitation; status mismatches
 * and residual exceptions are monitoring signals.
 */
function controlTreatment(ghost: number, mismatches: number, exceptions: number): {
  label: string;
  tone: StatusTone;
  detail: string;
} {
  if (ghost > 0) {
    return {
      label: 'Accepted',
      tone: 'neutral',
      detail: `${formatCount(ghost)} ghost record${ghost === 1 ? '' : 's'}`,
    };
  }
  if (mismatches > 0) {
    return {
      label: 'Monitor',
      tone: 'warning',
      detail: `${formatCount(mismatches)} status mismatch${mismatches === 1 ? '' : 'es'}`,
    };
  }
  if (exceptions > 0) {
    return {
      label: 'Monitor',
      tone: 'warning',
      detail: `${formatCount(exceptions)} observation${exceptions === 1 ? '' : 's'}`,
    };
  }
  return { label: 'Clean', tone: 'favourable', detail: 'No observations' };
}

export function WorkforceCapacity() {
  const trend = useQuery(getWorkforceTrend, []);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    if (selected || !trend.data?.length) return;
    const latestActual = [...trend.data].reverse().find((m) => m.period_type === 'Actual');
    setSelected((latestActual ?? trend.data[trend.data.length - 1]).month_iso);
  }, [selected, trend.data]);

  const departments = useQuery(
    () => (selected ? getWorkforceDepartments(selected) : Promise.resolve([])),
    [selected],
  );

  const current = trend.data?.find((m) => m.month_iso === selected) ?? null;
  const lastActual = useMemo(
    () => [...(trend.data ?? [])].reverse().find((m) => m.period_type === 'Actual') ?? null,
    [trend.data],
  );
  const lastMonth = trend.data?.[trend.data.length - 1] ?? null;

  // Payroll/FTE only exist through the workforce plan; 2027 carries hiring
  // pressure only. Null (not zero) beyond the data so the lines stop cleanly,
  // and split actual vs plan series (plan re-anchors on the last actual month
  // so the dashed line connects).
  const costRows = useMemo(() => {
    const rows = (trend.data ?? []).filter((r) => r.period_type !== 'Hiring plan');
    const lastActualIndex = rows.reduce(
      (latest, row, index) => (row.period_type === 'Actual' ? index : latest),
      -1,
    );
    return rows.map((r, index) => ({
      month_label: r.month_label,
      payroll_actual: r.period_type === 'Actual' ? r.payroll_cost : null,
      fte_actual: r.period_type === 'Actual' ? r.active_fte : null,
      payroll_plan: index >= lastActualIndex ? r.payroll_cost : null,
      fte_plan: index >= lastActualIndex ? r.active_fte : null,
    }));
  }, [trend.data]);

  const pressureRows = useMemo(
    () => (trend.data ?? []).filter((r) => r.period_type !== 'Actual'),
    [trend.data],
  );

  const peakPressure = useMemo(
    () =>
      pressureRows.reduce<(typeof pressureRows)[number] | null>(
        (peak, row) => (row.open_positions > (peak?.open_positions ?? 0) ? row : peak),
        null,
      ),
    [pressureRows],
  );

  const narrative = useMemo(() => {
    if (!current) return '';
    const topDept = departments.data?.[0];
    const planClause = peakPressure
      ? `Hiring pressure peaks at ${formatCount(peakPressure.open_positions)} open positions in ${peakPressure.month_label}, carrying ${formatGbp(peakPressure.open_position_monthly_exposure)} of monthly salary exposure. `
      : '';
    const controlClause =
      current.ghost_headcount > 0
        ? `Workforce controls flag ${formatCount(current.ghost_headcount)} ghost record${current.ghost_headcount === 1 ? '' : 's'} on payroll — an accepted limitation under the model-readiness policy; none are model-blocking.`
        : current.status_mismatches > 0 || current.control_exceptions > 0
          ? `${formatCount(Math.max(current.status_mismatches, current.control_exceptions))} workforce monitoring observation${Math.max(current.status_mismatches, current.control_exceptions) === 1 ? '' : 's'} in the period — none are model-blocking.`
          : 'No workforce control observations are flagged in the selected period.';
    if (current.period_type === 'Hiring plan') {
      return (
        `${current.month_label} sits in the hiring-plan horizon: payroll and headcount are not modelled beyond Dec 2026. ` +
        `The month carries ${formatCount(current.open_positions)} open position${current.open_positions === 1 ? '' : 's'} with ${formatGbp(current.open_position_monthly_exposure)} of monthly salary exposure. ` +
        planClause +
        controlClause
      );
    }
    return (
      `As at ${current.month_label}${current.period_type === 'Plan' ? ' (plan)' : ''}, workforce cost is ${formatGbp(current.payroll_cost)} across ` +
      `${formatCount(current.active_headcount)} active heads (${formatCount(current.active_fte)} FTE), or ` +
      `${current.payroll_per_fte == null ? 'n/a' : formatGbp(current.payroll_per_fte)} per FTE. ` +
      `${topDept ? `${topDept.department} is the largest payroll department at ${formatGbp(topDept.payroll_cost)}. ` : ''}` +
      `${planClause}` +
      controlClause
    );
  }, [current, departments.data, peakPressure]);

  const anyError = trend.error || departments.error;
  if (anyError) {
    return <div className="error-box"><strong>Could not load data.</strong><div>{anyError.message}</div></div>;
  }
  if (!current) {
    return (
      <div className="state">
        <div className="spinner" />
        <div>Loading workforce capacity...</div>
      </div>
    );
  }

  const months = trend.data ?? [];
  const years = [...new Set(months.map((m) => m.month_iso.slice(0, 4)))];
  const selectedYear = (selected ?? '').slice(0, 4);
  const monthsInYear = months.filter((m) => m.month_iso.startsWith(selectedYear));
  const selectYear = (year: string) => {
    const candidates = months.filter((m) => m.month_iso.startsWith(year));
    const preferred =
      [...candidates].reverse().find((m) => m.period_type === 'Actual') ??
      candidates[candidates.length - 1];
    if (preferred) setSelected(preferred.month_iso);
  };

  const isHiringPlanMonth = current.period_type === 'Hiring plan';
  const currentTreatment = controlTreatment(
    current.ghost_headcount,
    current.status_mismatches,
    current.control_exceptions,
  );

  return (
    <>
      <TopBar
        title="Workforce Capacity & Hiring Pressure"
        subtitle="Is workforce cost scaling with the business — and what hiring pressure is coming?"
        actions={
          <>
            <span className="scope-pill">Payroll actuals to {lastActual?.month_label ?? '-'}</span>
            <span className="scope-pill">Plan to {lastMonth?.month_label ?? '-'}</span>
            <select
              className="month-select"
              value={selectedYear}
              onChange={(e) => selectYear(e.target.value)}
              aria-label="Workforce reporting year"
            >
              {years.map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
            <select
              className="month-select"
              value={selected ?? ''}
              onChange={(e) => setSelected(e.target.value)}
              aria-label="Workforce reporting month"
            >
              {monthsInYear.map((m) => (
                <option key={m.month_iso} value={m.month_iso}>
                  {m.month_label.split(' ')[0]}
                  {m.period_type === 'Actual' ? '' : m.period_type === 'Plan' ? ' (plan)' : ' (hiring plan)'}
                </option>
              ))}
            </select>
          </>
        }
      />

      <div className="kpi-grid">
        <KpiCard
          label="Payroll Cost"
          value={isHiringPlanMonth ? '-' : formatGbpCompact(current.payroll_cost)}
          sub={isHiringPlanMonth ? 'payroll not modelled in hiring plan' : `${current.month_label}${current.period_type === 'Plan' ? ' (plan)' : ''}`}
        />
        <KpiCard
          label="Active Headcount"
          value={isHiringPlanMonth ? '-' : formatCount(current.active_headcount)}
          sub={isHiringPlanMonth ? 'headcount not modelled in hiring plan' : `${formatCount(current.active_fte)} FTE`}
        />
        <KpiCard
          label="Payroll per FTE"
          value={isHiringPlanMonth || current.payroll_per_fte == null ? '-' : formatGbpCompact(current.payroll_per_fte)}
          sub="fully loaded monthly cost"
        />
        <KpiCard
          label="Open Positions"
          value={formatCount(current.open_positions)}
          sub={`${formatGbpCompact(current.open_position_monthly_exposure)} monthly exposure`}
          status={{ tone: current.open_positions > 0 ? 'warning' : 'neutral', label: current.open_positions > 0 ? 'Pressure' : 'None' }}
        />
        <KpiCard
          label="Control Observations"
          value={formatCount(current.control_exceptions)}
          sub={current.ghost_headcount > 0 ? `covering ${currentTreatment.detail}` : currentTreatment.detail}
          status={{ tone: currentTreatment.tone, label: currentTreatment.label }}
        />
      </div>

      <div className="panel-grid">
        <ChartCard
          className="hero"
          title="Workforce cost and FTE"
          subtitle={`Actuals to ${lastActual?.month_label ?? '-'}; dashed plan to Dec 2026 — 2027 carries hiring pressure only`}
        >
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={costRows} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="month_label" stroke={AXIS} fontSize={11} tickLine={false} minTickGap={24} />
              <YAxis yAxisId="money" stroke={AXIS} fontSize={11} tickLine={false} width={56} tickFormatter={(v: number) => formatGbpCompact(v)} />
              <YAxis yAxisId="count" orientation="right" stroke={AXIS} fontSize={11} tickLine={false} width={44} tickFormatter={(v: number) => formatCount(v)} />
              <Tooltip
                contentStyle={{ background: '#ffffff', border: '1px solid #d6d3cb', borderRadius: 8, color: '#1a1a1a' }}
                formatter={(v: number, name: string) => [
                  name.startsWith('payroll') ? formatGbp(v) : formatCount(v),
                  COST_SERIES_LABELS[name] ?? name,
                ]}
              />
              <Legend formatter={(v: string) => COST_SERIES_LABELS[v] ?? v} />
              {lastActual && (
                <ReferenceLine
                  yAxisId="money"
                  x={lastActual.month_label}
                  stroke={AXIS}
                  strokeDasharray="4 4"
                  label={{ value: 'plan →', position: 'insideTopRight', fill: AXIS, fontSize: 10 }}
                />
              )}
              <Line yAxisId="money" type="monotone" dataKey="payroll_actual" stroke={chart.primary} strokeWidth={2.4} dot={false} connectNulls={false} />
              <Line yAxisId="money" type="monotone" dataKey="payroll_plan" stroke={chart.primary} strokeWidth={1.8} strokeDasharray="5 4" dot={false} connectNulls={false} />
              <Line yAxisId="count" type="monotone" dataKey="fte_actual" stroke={chart.secondary} strokeWidth={2} dot={false} connectNulls={false} />
              <Line yAxisId="count" type="monotone" dataKey="fte_plan" stroke={chart.secondary} strokeWidth={1.6} strokeDasharray="5 4" dot={false} connectNulls={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Future hiring pressure"
          subtitle="Jul 2026 - Dec 2027 plan horizon: open roles and monthly salary exposure"
        >
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={pressureRows} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="month_label" stroke={AXIS} fontSize={11} tickLine={false} minTickGap={18} />
              <YAxis yAxisId="count" stroke={AXIS} fontSize={11} tickLine={false} width={30} allowDecimals={false} tickFormatter={(v: number) => formatCount(v)} />
              <YAxis yAxisId="money" orientation="right" stroke={AXIS} fontSize={11} tickLine={false} width={52} tickFormatter={(v: number) => formatGbpCompact(v)} />
              <Tooltip
                cursor={{ fill: 'rgba(0,0,0,0.03)' }}
                contentStyle={{ background: '#ffffff', border: '1px solid #d6d3cb', borderRadius: 8, color: '#1a1a1a' }}
                formatter={(v: number, name: string) => [
                  name === 'open_position_monthly_exposure' ? formatGbp(v) : formatCount(v),
                  name === 'open_position_monthly_exposure' ? 'Monthly salary exposure' : 'Open positions',
                ]}
              />
              <Legend
                formatter={(v: string) =>
                  v === 'open_position_monthly_exposure' ? 'Monthly salary exposure' : 'Open positions'
                }
              />
              <Bar yAxisId="count" dataKey="open_positions" fill={chart.amber} radius={[2, 2, 0, 0]} />
              <Line yAxisId="money" type="monotone" dataKey="open_position_monthly_exposure" stroke={chart.secondary} strokeWidth={2} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <div className="panel" style={{ marginTop: 12, paddingBottom: 16 }}>
        <div className="panel-head">
          <div>
            <h3>Department capacity</h3>
            <p className="panel-sub">{current.month_label} - payroll, active headcount and open roles</p>
          </div>
        </div>
        <div className="table-scroll">
          <table className="pnl">
            <thead>
              <tr>
                <th className="row-label">Department</th>
                <th>Payroll</th>
                <th>Headcount</th>
                <th>Open roles</th>
                <th className="row-label">Control treatment</th>
              </tr>
            </thead>
            <tbody>
              {(departments.data ?? []).map((d) => {
                const treatment = controlTreatment(d.ghost_headcount, d.status_mismatches, d.control_exceptions);
                return (
                  <tr key={d.department}>
                    <td className="row-label">{d.department}</td>
                    <td>{formatGbp(d.payroll_cost)}</td>
                    <td>{formatCount(d.active_headcount)}</td>
                    <td>{formatCount(d.open_positions)}</td>
                    <td className="row-label">
                      <StatusPill tone={treatment.tone} label={treatment.label} />
                      {treatment.label !== 'Clean' && (
                        <span className="control-detail">{treatment.detail}</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="pnl-note">
          Under the model-readiness policy, workforce observations are accepted limitations
          (ghost records) or monitoring signals (status mismatches) — none are model-blocking.
        </p>
      </div>

      <div className="narrative">
        <h3>Workforce commentary</h3>
        <p>{narrative}</p>
      </div>
    </>
  );
}
