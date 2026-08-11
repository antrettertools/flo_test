/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  // maplibre-gl loads its style/tile-processing worker via a
  // `new URL(..., import.meta.url)`-relative path. Vite's dependency
  // pre-bundling rewrites that import.meta.url context, so the worker
  // request resolves to a nonexistent .vite/deps/maplibre-gl-worker.mjs
  // (404) instead of the real file in maplibre-gl/dist -- the worker then
  // never loads, and since maplibre-gl does its style/source processing off
  // the main thread, the map's 'load' event never fires (silently, with no
  // console error). Excluding it from pre-bundling serves it as-is from
  // node_modules, preserving the correct relative worker URL.
  optimizeDeps: {
    exclude: ['maplibre-gl'],
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/setupTests.ts',
  },
});
