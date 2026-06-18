import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const dashboardRoot = resolve(here, '..');
const repoRoot = resolve(dashboardRoot, '..');
const dataDir = join(dashboardRoot, 'public', 'data');
const config = JSON.parse(
  await readFile(join(dashboardRoot, 'data-files.json'), 'utf8'),
);

function gitCommit() {
  if (process.env.GITHUB_SHA) return process.env.GITHUB_SHA;
  try {
    return execFileSync('git', ['rev-parse', 'HEAD'], {
      cwd: repoRoot,
      encoding: 'utf8',
    }).trim();
  } catch {
    return 'unknown';
  }
}

const files = [];
for (const entry of config.files) {
  const filename = `${entry.name}.parquet`;
  const buffer = await readFile(join(dataDir, filename));
  files.push({
    name: filename,
    bytes: buffer.byteLength,
    sha256: createHash('sha256').update(buffer).digest('hex'),
    source: entry.source,
  });
}

const manifest = {
  schemaVersion: 1,
  generatedAt: new Date().toISOString(),
  gitCommit: gitCommit(),
  files,
};

await writeFile(
  join(dataDir, 'manifest.json'),
  `${JSON.stringify(manifest, null, 2)}\n`,
  'utf8',
);

console.log(`Wrote dashboard data manifest for ${files.length} files.`);
