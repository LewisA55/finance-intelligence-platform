import { useEffect, useMemo, useState } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { useQuery } from '../hooks/useQuery';
import { getWorkforceDepartments, getWorkforceTrend } from '../duckdb/queries';
import { TopBar } from '../components/TopBar';
import { KpiCard } from '../components/KpiCard';
import { ChartCard } from '../components/ChartCard';
import { StatusPill } from '../components/StatusPill';
import { chart } from '../lib/theme';
import { formatCount, formatGbp, formatGbpCompact } from '../lib/format';

const GRID = chart.grid;
const AXIS = chart.axis;

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
  const latestPlan = useMemo(
    () => [...(trend.data ?? [])].reverse().find((m) => m.period_type === 'Plan') ?? null,
    [trend.data],
  );

  const futurePressure = useMemo(() => {
    const rows = trend.data ?? [];
    return rows
      .filter((r) => r.period_type === 'Plan')
      .map((r) => ({
        month_label: r.month_label,
        month_iso: r.month_iso,
        open_positions: r.open_positions,
        open_position_monthly_exposure: r.open_position_monthly_exposure,
      }));
  }, [trend.data]);

  const narrative = useMemo(() => {
    if (!current) return '';
    const topDept = departments.data?.[0];
    const planClause = latestPlan
      ? `Future hiring pressure peaks at ${formatCount(latestPlan.open_positions)} open positions by ${latestPlan.month_label}, representing ${formatGbp(latestPlan.open_position_monthly_exposure)} of monthly salary exposure. `
      : '';
    return (
      `As at ${current.month_label}, workforce cost is ${formatGbp(current.payroll_cost)} across ` +
      `${formatCount(current.active_headcount)} active heads (${formatCount(current.active_fte)} FTE), or ` +
      `${current.payroll_per_fte == null ? 'n/a' : formatGbp(current.payroll_per_fte)} per FTE. ` +
      `${topDept ? `${topDept.department} is the largest payroll department at ${formatGbp(topDept.payroll_cost)}. ` : ''}` +
      `${planClause}` +
      `${current.control_exceptions > 0 ? `${formatCount(current.control_exceptions)} workforce control observations need review.` : 'No workforce control observations are flagged in the selected period.'}`
    );
  }, [current, departments.data, latestPlan]);

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

  return (
    <>
      <TopBar
        title="Workforce Capacity"
        subtitle="Payroll cost, FTE capacity, hiring pressure and HRIS controls"
        actions={
          <>
            <span className="scope-pill">Actual + plan horizon</span>
            <select
              className="month-select"
              value={selected ?? ''}
              onChange={(e) => setSelected(e.target.value)}
              aria-label="Workforce reporting month"
            >
              {(trend.data ?? []).map((m) => (
                <option key={m.month_iso} value={m.month_iso}>
                  {m.month_label}
                  {m.period_type === 'Plan' ? ' (plan)' : ''}
                </option>
              ))}
            </select>
          </>
        }
      />

      <div className="kpi-grid">
        <KpiCard label="Payroll Cost" value={formatGbpCompact(current.payroll_cost)} sub={current.month_label} />
        <KpiCard label="Active Headcount" value={formatCount(current.active_headcount)} sub={`${formatCount(current.active_fte)} FTE`} />
        <KpiCard label="Payroll per FTE" value={current.payroll_per_fte == null ? '-' : formatGbpCompact(current.payroll_per_fte)} sub="fully loaded monthly cost" />
        <KpiCard
          label="Open Positions"
          value={formatCount(current.open_positions)}
          sub={`${formatGbpCompact(current.open_position_monthly_exposure)} monthly exposure`}
          status={{ tone: current.open_positions > 0 ? 'warning' : 'neutral', label: current.open_positions > 0 ? 'Pressure' : 'None' }}
        />
        <KpiCard
          label="Control Observations"
          value={formatCount(current.control_exceptions)}
          sub={`${formatCount(current.ghost_headcount)} ghost headcount`}
          status={{ tone: current.control_exceptions > 0 ? 'warning' : 'favourable', label: current.control_exceptions > 0 ? 'Review' : 'Clean' }}
        />
      </div>

      <div className="panel-grid">
        <ChartCard title="Workforce cost and FTE" subtitle="Jan 2022-Dec 2027: actuals and planned horizon">
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={trend.data ?? []} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="month_label" stroke={AXIS} fontSize={11} tickLine={false} minTickGap={24} />
              <YAxis yAxisId="money" stroke={AXIS} fontSize={11} tickLine={false} width={56} tickFormatter={(v: number) => formatGbpCompact(v)} />
              <YAxis yAxisId="count" orientation="right" stroke={AXIS} fontSize={11} tickLine={false} width={44} tickFormatter={(v: number) => formatCount(v)} />
              <Tooltip
                contentStyle={{ background: '#ffffff', border: '1px solid #d6d3cb', borderRadius: 8, color: '#1a1a1a' }}
                formatter={(v: number, name) => [
                  name === 'payroll_cost' ? formatGbp(v) : formatCount(v),
                  name === 'payroll_cost' ? 'Payroll cost' : 'FTE',
                ]}
              />
              <Legend formatter={(v) => (v === 'payroll_cost' ? 'Payroll cost' : 'Active FTE')} />
              <Line yAxisId="money" type="monotone" dataKey="payroll_cost" stroke={chart.primary} strokeWidth={2.4} dot={false} />
              <Line yAxisId="count" type="monotone" dataKey="active_fte" stroke={chart.secondary} strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Future hiring pressure" subtitle="Open roles and monthly salary exposure">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={futurePressure} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="month_label" stroke={AXIS} fontSize={11} tickLine={false} minTickGap={18} />
              <YAxis stroke={AXIS} fontSize={11} tickLine={false} width={44} tickFormatter={(v: number) => formatCount(v)} />
              <Tooltip
                cursor={{ fill: 'rgba(0,0,0,0.03)' }}
                contentStyle={{ background: '#ffffff', border: '1px solid #d6d3cb', borderRadius: 8, color: '#1a1a1a' }}
                formatter={(v: number, name) => [
                  name === 'open_position_monthly_exposure' ? formatGbp(v) : formatCount(v),
                  name === 'open_position_monthly_exposure' ? 'Monthly exposure' : 'Open positions',
                ]}
              />
              <Bar dataKey="open_positions" fill={chart.amber} radius={[2, 2, 0, 0]} />
            </BarChart>
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
                <th className="row-label">Control status</th>
              </tr>
            </thead>
            <tbody>
              {(departments.data ?? []).map((d) => (
                <tr key={d.department}>
                  <td className="row-label">{d.department}</td>
                  <td>{formatGbp(d.payroll_cost)}</td>
                  <td>{formatCount(d.active_headcount)}</td>
                  <td>{formatCount(d.open_positions)}</td>
                  <td className="row-label">
                    <StatusPill
                      tone={d.control_exceptions > 0 ? 'warning' : 'favourable'}
                      label={d.control_exceptions > 0 ? 'Review' : 'Clean'}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="narrative">
        <h3>Workforce commentary</h3>
        <p>{narrative}</p>
      </div>
    </>
  );
}
