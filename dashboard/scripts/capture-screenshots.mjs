import { spawn } from 'node:child_process';
import { access, mkdir } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const here = dirname(fileURLToPath(import.meta.url));
const dashboardRoot = resolve(here, '..');
const repoRoot = resolve(dashboardRoot, '..');
const outputDir = join(repoRoot, 'docs', 'img');
const port = Number(process.env.ATLAS_SCREENSHOT_PORT ?? 4174);
const baseUrl = process.env.ATLAS_SCREENSHOT_URL ?? `http://127.0.0.1:${port}`;
const browserCandidates = [
  process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
].filter(Boolean);

let executablePath;
for (const candidate of browserCandidates) {
  try {
    await access(candidate);
    executablePath = candidate;
    break;
  } catch {
    // Try the next installed browser.
  }
}
if (!executablePath) {
  throw new Error('Chrome or Edge was not found. Set PLAYWRIGHT_CHROMIUM_EXECUTABLE.');
}

await mkdir(outputDir, { recursive: true });

let server;
if (!process.env.ATLAS_SCREENSHOT_URL) {
  server = spawn(
    process.execPath,
    [
      join(dashboardRoot, 'node_modules', 'vite', 'bin', 'vite.js'),
      '--host',
      '127.0.0.1',
      '--port',
      String(port),
    ],
    {
      cwd: dashboardRoot,
      stdio: 'ignore',
    },
  );
}

async function waitForServer() {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    try {
      const response = await fetch(baseUrl);
      if (response.ok) return;
    } catch {
      // Server is still starting.
    }
    await new Promise((resolveWait) => setTimeout(resolveWait, 500));
  }
  throw new Error(`Dashboard did not start at ${baseUrl}`);
}

async function waitForDashboard(page) {
  await page.waitForSelector('.pack-header');
  await page.waitForSelector('.spinner', { state: 'detached', timeout: 45_000 });
  try {
    await page.waitForFunction(() => {
      const meta = document.querySelector('.pack-meta')?.textContent ?? '';
      return meta.includes('BUILT') && !meta.includes('—');
    }, { timeout: 15_000 });
  } catch {
    const error = await page
      .locator('.pack-meta')
      .getAttribute('data-provenance-error');
    throw new Error(`Pack provenance did not load: ${error ?? 'unknown error'}`);
  }
  await page.waitForTimeout(800);
}

async function capturePage(page, id, filename, targetHeading) {
  await page.goto(`${baseUrl}/#/${id}`, { waitUntil: 'networkidle' });
  await waitForDashboard(page);

  if (targetHeading) {
    const heading = page.getByRole('heading', { name: targetHeading });
    await heading.evaluate((element) => {
      const top = element.getBoundingClientRect().top + window.scrollY - 24;
      window.scrollTo({ top, behavior: 'instant' });
    });
    await page.waitForTimeout(300);
  } else {
    await page.evaluate(() => window.scrollTo(0, 0));
  }

  await page.screenshot({
    path: join(outputDir, filename),
    fullPage: false,
  });
  console.log(`captured ${filename}`);
}

try {
  await waitForServer();
  const browser = await chromium.launch({ executablePath, headless: true });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
    deviceScaleFactor: 1,
  });

  await capturePage(page, 'command-center', 'command-center.png');
  await capturePage(
    page,
    'saas',
    'saas-performance.png',
    'Active ARR by product & segment',
  );
  await capturePage(page, 'revenue', 'revenue-recognition.png');
  await capturePage(
    page,
    'working-capital',
    'working-capital.png',
    'Collection rate by region',
  );
  await capturePage(page, 'control-tower', 'control-tower.png');

  await browser.close();
} finally {
  server?.kill();
}
