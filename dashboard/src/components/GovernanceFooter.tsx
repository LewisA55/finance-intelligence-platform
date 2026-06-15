/**
 * Trust-chain footer: synthetic source -> dbt controls -> governed mart ->
 * DuckDB-WASM in the browser. States provenance on every page.
 */
export function GovernanceFooter() {
  return (
    <footer className="governance-footer">
      <span>
        Source: <code>gold.mart_executive_cfo_command_center</code>
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
