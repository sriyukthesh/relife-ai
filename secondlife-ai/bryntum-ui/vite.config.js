import { defineConfig } from 'vite';
import { resolve } from 'path';

// Builds into the FastAPI app's static directory.
export default defineConfig({
  base: './',
  build: {
    outDir: '../backend/sl_ui/timeline',
    emptyOutDir: true,
    rollupOptions: {
      // Three separate pages on purpose: Bryntum Gantt and Scheduler each ship their own core,
      // so they are isolated in iframes instead of sharing one JS/CSS scope.
      input: {
        main: resolve(__dirname, 'index.html'),
        gantt: resolve(__dirname, 'gantt.html'),
        scheduler: resolve(__dirname, 'scheduler.html'),
      },
    },
  },
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
});
