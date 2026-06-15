// Copies the committed dashboard data slice from the dbt parquet exports into
// public/data. Run after a fresh `dbt build` + parquet export:
//   npm run refresh-data
import { copyFile, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, '..', '..');
const exportDir = join(repoRoot, 'data', 'exports', 'powerbi', 'parquet');
const targetDir = join(here, '..', 'public', 'data');

// Keep this list in sync with DATA_FILES in src/duckdb/client.ts.
const FILES = [
  'mart_executive_cfo_command_center.parquet',
  'mart_financial_performance.parquet',
  'mart_ap_working_capital_control.parquet',
  'dim_region.parquet',
  'dim_date.parquet',
  'dim_department.parquet',
];

await mkdir(targetDir, { recursive: true });
for (const file of FILES) {
  await copyFile(join(exportDir, file), join(targetDir, file));
  console.log(`copied ${file}`);
}
console.log(`\nRefreshed ${FILES.length} files into public/data.`);
