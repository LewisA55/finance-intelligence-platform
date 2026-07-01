import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const dashboardRoot = resolve(here, '..');
const dataDir = join(dashboardRoot, 'public', 'data');
const config = JSON.parse(
  await readFile(join(dashboardRoot, 'data-files.json'), 'utf8'),
);
const manifest = JSON.parse(
  await readFile(join(dataDir, 'manifest.json'), 'utf8'),
);
const manifestFiles = new Map(manifest.files.map((file) => [file.name, file]));

const errors = [];
for (const entry of config.files) {
  const format = entry.format ?? 'parquet';
  const filename = `${entry.name}.${format}`;
  const expected = manifestFiles.get(filename);
  if (!expected) {
    errors.push(`${filename}: missing from manifest`);
    continue;
  }

  try {
    const buffer = await readFile(join(dataDir, filename));
    const sha256 = createHash('sha256').update(buffer).digest('hex');
    if (buffer.byteLength !== expected.bytes) {
      errors.push(`${filename}: size does not match manifest`);
    }
    if (sha256 !== expected.sha256) {
      errors.push(`${filename}: hash does not match manifest`);
    }
  } catch {
    errors.push(`${filename}: required file is missing`);
  }
}

const unexpected = manifest.files
  .map((file) => file.name)
  .filter((name) => !config.files.some((entry) => `${entry.name}.${entry.format ?? 'parquet'}` === name));
for (const name of unexpected) errors.push(`${name}: unexpected manifest entry`);

if (errors.length) {
  console.error('Dashboard data validation failed:');
  for (const error of errors) console.error(`- ${error}`);
  process.exit(1);
}

console.log(
  `Dashboard data validated: ${config.files.length} files, manifest schema ${manifest.schemaVersion}.`,
);
