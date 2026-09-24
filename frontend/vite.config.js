import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Ported from D:\projects\Sentinel_Repo\ui\vite.config.js (F52).
// The API (and the HLS relay) run on :8000; proxy /api AND /crops during
// dev so the browser talks to one origin and the sentinel_session cookie
// carries every call (decision F41 — no key dialog).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/crops': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
