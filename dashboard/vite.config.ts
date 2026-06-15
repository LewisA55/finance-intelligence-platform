import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// On `vite build` the base is the GitHub Pages project subpath (must match the
// repo name); local dev/preview-from-source uses '/'. This keeps the deployed
// asset/data URLs correct on Pages while leaving local dev simple.
export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/finance-intelligence-platform/' : '/',
  plugins: [react()],
  // DuckDB-WASM ships large prebuilt wasm; don't let Vite pre-bundle it.
  optimizeDeps: {
    exclude: ['@duckdb/duckdb-wasm'],
  },
  build: {
    target: 'esnext',
  },
}));
