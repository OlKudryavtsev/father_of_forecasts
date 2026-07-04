import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { readFileSync } from 'node:fs';

const packageVersion = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf-8')).version;

export default defineConfig({
  base: '/miniapp-static/',
  define: { __APP_VERSION__: JSON.stringify(packageVersion) },
  plugins: [react()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
