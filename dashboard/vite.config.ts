import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Relative base so the static build works on GitHub Pages project subpaths
// (e.g. /finance-intelligence-platform/) and on Vercel (/) without changes.
export default defineConfig({
  base: './',
  plugins: [react()],
  // DuckDB-WASM ships large prebuilt wasm; don't let Vite try to pre-bundle it.
  optimizeDeps: {
    exclude: ['@duckdb/duckdb-wasm'],
  },
  build: {
    target: 'esnext',
  },
});
