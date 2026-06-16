import * as duckdb from '@duckdb/duckdb-wasm';
import mvpWasm from '@duckdb/duckdb-wasm/dist/duckdb-mvp.wasm?url';
import mvpWorker from '@duckdb/duckdb-wasm/dist/duckdb-browser-mvp.worker.js?url';
import ehWasm from '@duckdb/duckdb-wasm/dist/duckdb-eh.wasm?url';
import ehWorker from '@duckdb/duckdb-wasm/dist/duckdb-browser-eh.worker.js?url';

// Parquet slices shipped in /public/data; each becomes a queryable view of the
// same name. Keep this list lean: the browser downloads every file, so we ship
// curated, pre-aggregated executive slices rather than the raw detail marts.
const DATA_FILES = [
  'mart_executive_cfo_command_center',
  'mart_financial_performance',
  'mart_ap_working_capital_control',
  'mart_saas_arr_by_product_segment',
  'mart_saas_retention_by_segment',
  'mart_o2c_top_customers',
  'mart_o2c_by_region_segment',
  'dim_region',
  'dim_date',
  'dim_department',
] as const;

let dbPromise: Promise<duckdb.AsyncDuckDB> | null = null;
let connPromise: Promise<duckdb.AsyncDuckDBConnection> | null = null;

// Self-hosted bundles: Vite emits these assets into the build output and serves
// them same-origin, so there is no CDN dependency at runtime (offline-capable).
// The browser downloads only the single bundle selectBundle picks.
const MANUAL_BUNDLES: duckdb.DuckDBBundles = {
  mvp: { mainModule: mvpWasm, mainWorker: mvpWorker },
  eh: { mainModule: ehWasm, mainWorker: ehWorker },
};

async function createDatabase(): Promise<duckdb.AsyncDuckDB> {
  // Picks the eh (exception-handling) build where supported, else the mvp fallback.
  const bundle = await duckdb.selectBundle(MANUAL_BUNDLES);

  // Worker assets are served same-origin, so no Blob/importScripts shim is needed.
  const worker = new Worker(bundle.mainWorker!);
  const logger = new duckdb.ConsoleLogger(duckdb.LogLevel.WARNING);
  const db = new duckdb.AsyncDuckDB(logger, worker);
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker ?? undefined);

  return db;
}

async function registerParquet(
  db: duckdb.AsyncDuckDB,
  conn: duckdb.AsyncDuckDBConnection,
): Promise<void> {
  const base = import.meta.env.BASE_URL; // honours Vite `base` for GH Pages subpaths
  for (const name of DATA_FILES) {
    const response = await fetch(`${base}data/${name}.parquet`);
    if (!response.ok) {
      throw new Error(`Failed to load ${name}.parquet (HTTP ${response.status})`);
    }
    const buffer = new Uint8Array(await response.arrayBuffer());
    await db.registerFileBuffer(`${name}.parquet`, buffer);
    await conn.query(
      `create or replace view ${name} as select * from read_parquet('${name}.parquet')`,
    );
  }
}

/** Lazily initialise DuckDB-WASM and register all parquet views (singleton). */
export function getConnection(): Promise<duckdb.AsyncDuckDBConnection> {
  if (!connPromise) {
    connPromise = (async () => {
      if (!dbPromise) dbPromise = createDatabase();
      const db = await dbPromise;
      const conn = await db.connect();
      await registerParquet(db, conn);
      return conn;
    })();
  }
  return connPromise;
}

/**
 * Run a SQL query and return plain JS objects. Arrow can hand back BigInt
 * (counts) and typed values; we coerce BigInt -> Number so the UI layer never
 * has to think about it. Cast money to ::double and counts to ::integer in SQL
 * to keep everything as clean primitives.
 */
export async function runQuery<T = Record<string, unknown>>(
  sql: string,
): Promise<T[]> {
  const conn = await getConnection();
  const result = await conn.query(sql);
  return result.toArray().map((row) => {
    const obj = row.toJSON() as Record<string, unknown>;
    for (const key of Object.keys(obj)) {
      if (typeof obj[key] === 'bigint') {
        obj[key] = Number(obj[key]);
      }
    }
    return obj as T;
  });
}
