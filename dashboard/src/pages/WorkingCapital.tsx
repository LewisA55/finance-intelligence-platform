import { PlaceholderPage } from '../components/PlaceholderPage';

export function WorkingCapital() {
  return (
    <PlaceholderPage
      title="Working Capital"
      subtitle="Order-to-cash collections and accounts-payable exposure"
      purpose="Track cash tied up in receivables and owed on payables, with ageing and collection performance, so the CFO can manage liquidity and counterparty risk."
      questions={[
        'What is open AR exposure and how is collection performance trending?',
        'What is open and overdue AP liability, and where is duplicate-payment risk?',
        'What is the net working-capital position by region and customer?',
      ]}
      sources={['mart_o2c_customer_collections', 'mart_ap_working_capital_control', 'dim_customer', 'dim_vendor']}
    />
  );
}
