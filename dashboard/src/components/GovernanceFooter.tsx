/**
 * Trust-chain footer: synthetic source -> dbt controls -> governed mart ->
 * DuckDB-WASM in the browser. States provenance on every page.
 */
export function GovernanceFooter({ current }: { current: PageId }) {
  return (
    <footer className="governance-footer">
      <span>
        Source: <code>{SOURCES[current]}</code>
      </span>
      <span className="gf-sep">·</span>
      <span>Scope-safe Company Total</span>
      <span className="gf-sep">·</span>
      <span>
        <span className="gf-check">✓</span> dbt validated
      </span>
      <span className="gf-sep">·</span>
      <span>DuckDB-WASM</span>
    </footer>
  );
}
import type { PageId } from '../nav';

const SOURCES: Record<PageId, string> = {
  'command-center': 'mart_executive_cfo_command_center',
  saas: 'executive mart + curated SaaS slices',
  financial: 'mart_financial_performance',
  revenue: 'mart_executive_cfo_command_center',
  'working-capital': 'executive mart + O2C/AP slices',
  'control-tower': 'mart_executive_cfo_command_center',
  validation: 'dashboard Parquet snapshot',
};
