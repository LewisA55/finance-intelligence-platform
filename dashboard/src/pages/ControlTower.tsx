import { PlaceholderPage } from '../components/PlaceholderPage';

export function ControlTower() {
  return (
    <PlaceholderPage
      title="Control Tower"
      subtitle="Governed control exceptions across the finance close"
      purpose="Surface the control telemetry the warehouse deliberately retains — revenue recognition, deferred revenue continuity, AP duplicates, workforce anomalies — so exceptions are visible and triaged rather than hidden."
      questions={[
        'Which control exceptions are open this month, and in which domains?',
        'Are deferred-revenue and revenue-recognition rollforwards continuous?',
        'What is the financial exposure attached to flagged exceptions?',
      ]}
      sources={['mart_deferred_revenue_control', 'mart_revenue_waterfall', 'mart_ap_working_capital_control', 'mart_workforce_cost_control']}
    />
  );
}
