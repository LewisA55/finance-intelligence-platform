// Runtime smoke test: serve the built dashboard and drive every hash route in
// a real browser, asserting each page renders governed data without errors.
// Build success alone is not enough — a dependency bump once changed DuckDB's
// SQL binder strictness and broke five pages that compiled cleanly.
//
// Usage: npm run test:smoke   (requires `npm run build` output in dist/)
// Local override: SMOKE_BROWSER_PATH=<chromium/edge exe> to skip the
// playwright-managed browser.
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { chromium } from 'playwright';

const dashboardDir = dirname(dirname(fileURLToPath(import.meta.url)));
const PORT = 4318;
const BASE = `http://localhost:${PORT}/finance-intelligence-platform/`;

const ROUTES = [
  { id: 'command-center', heading: 'CFO Command Center' },
  { id: 'saas', heading: 'SaaS Performance' },
  { id: 'financial', heading: 'Financial Performance' },
  { id: 'revenue', heading: 'Revenue Quality' },
  { id: 'working-capital', heading: 'Working Capital' },
  { id: 'workforce', heading: 'Workforce Capacity & Hiring Pressure' },
  { id: 'model', heading: 'Forecast & Valuation' },
  { id: 'control-tower', heading: 'Control Tower' },
  { id: 'validation', heading: 'Data & Validation' },
];

async function waitForServer(url, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {
      // server not up yet
    }
    await new Promise((r) => setTimeout(r, 300));
  }
  throw new Error(`Preview server did not respond at ${url} within ${timeoutMs}ms`);
}

// The config only applies the Pages subpath on `vite build`, so preview must be
// told the base explicitly or the built asset URLs 404.
const preview = spawn(
  process.execPath,
  [
    join(dashboardDir, 'node_modules', 'vite', 'bin', 'vite.js'),
    'preview',
    '--port', String(PORT),
    '--strictPort',
    '--base', '/finance-intelligence-platform/',
  ],
  { cwd: dashboardDir, stdio: 'ignore' },
);

let failures = 0;
try {
  await waitForServer(BASE);

  const browser = await chromium.launch({
    executablePath: process.env.SMOKE_BROWSER_PATH || undefined,
    headless: true,
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const pageErrors = [];
  page.on('pageerror', (e) => pageErrors.push(e.message));

  for (const route of ROUTES) {
    pageErrors.length = 0;
    await page.goto(`${BASE}#/${route.id}`, { waitUntil: 'load' });
    // Data pages resolve to either rendered content or an explicit error box.
    await page.waitForSelector('.kpi .value, .kv li, table.pnl td, .error-box', { timeout: 90000 });
    await page.waitForTimeout(1500); // let remaining queries settle

    const result = await page.evaluate(() => ({
      heading: document.querySelector('.topbar h2')?.textContent?.trim() ?? '',
      errorBox: document.querySelector('.error-box')?.textContent?.trim() ?? null,
      hasContent: !!document.querySelector('.kpi .value, .kv li, table.pnl td'),
    }));

    const problems = [];
    if (result.errorBox) problems.push(`error box: ${result.errorBox.slice(0, 160)}`);
    if (!result.heading.includes(route.heading)) {
      problems.push(`heading "${result.heading}" does not include "${route.heading}"`);
    }
    if (!result.hasContent) problems.push('no data content rendered');
    if (pageErrors.length) problems.push(`page errors: ${pageErrors.join(' | ').slice(0, 200)}`);

    if (problems.length) {
      failures++;
      console.error(`FAIL  #/${route.id}\n      ${problems.join('\n      ')}`);
    } else {
      console.log(`ok    #/${route.id} — "${result.heading}"`);
    }
  }

  await browser.close();
} finally {
  preview.kill();
}

if (failures > 0) {
  console.error(`\nSmoke test failed: ${failures} of ${ROUTES.length} routes broken.`);
  process.exit(1);
}
console.log(`\nSmoke test passed: ${ROUTES.length} routes render governed data.`);
