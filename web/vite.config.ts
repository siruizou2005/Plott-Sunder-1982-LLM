import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The built bundle goes to web/dist, which the Express server mounts at "/".
// In dev, /ws and /api are proxied to that same server on :8100.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: '/',
  build: { outDir: 'dist', emptyOutDir: true },
  server: {
    port: 5273,
    proxy: {
      '/ws': { target: 'ws://127.0.0.1:8100', ws: true },
      '/api': 'http://127.0.0.1:8100',
    },
  },
})
