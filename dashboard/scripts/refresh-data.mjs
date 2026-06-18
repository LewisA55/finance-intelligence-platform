// Refreshes the complete committed dashboard snapshot. Run after a fresh
// `dbt build` + parquet export:
//   npm run refresh-data
import { copyFile, mkdir, readFile } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, '..', '..');
const exportDir = join(repoRoot, 'data', 'exports', 'powerbi', 'parquet');
const targetDir = join(here, '..', 'public', 'data');

const config = JSON.parse(
  await readFile(join(here, '..', 'data-files.json'), 'utf8'),
);
const exportedFiles = config.files.filter((file) => file.source === 'export');

function runDbtMacro(name) {
  const result = spawnSync('dbt', ['run-operation', name], {
    cwd: repoRoot,
    stdio: 'inherit',
    shell: process.platform === 'win32',
  });
  if (result.status !== 0) {
    throw new Error(`dbt run-operation ${name} failed`);
  }
}

await mkdir(targetDir, { recursive: true });
for (const entry of exportedFiles) {
  const filename = `${entry.name}.parquet`;
  await copyFile(join(exportDir, filename), join(targetDir, filename));
  console.log(`copied ${filename}`);
}

runDbtMacro('export_saas_aggregates');
runDbtMacro('export_o2c_aggregates');

const manifest = spawnSync(
  process.execPath,
  [join(here, 'data-manifest.mjs')],
  { cwd: repoRoot, stdio: 'inherit' },
);
if (manifest.status !== 0) throw new Error('Failed to generate dashboard data manifest');

const validation = spawnSync(
  process.execPath,
  [join(here, 'validate-data.mjs')],
  { cwd: repoRoot, stdio: 'inherit' },
);
if (validation.status !== 0) throw new Error('Dashboard data validation failed');

console.log(`\nRefreshed ${config.files.length} files into public/data.`);
