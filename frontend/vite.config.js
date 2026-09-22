import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server host/port: WEB_HOST / WEB_PORT (defaults for local work).
// API target:     API_HOST / API_PORT (the FastAPI service).
const apiTarget = `http://${process.env.API_HOST || '127.0.0.1'}:${
  process.env.API_PORT || '8000'
}`

export default defineConfig({
  plugins: [react()],
  server: {
    host: process.env.WEB_HOST || '0.0.0.0',
    port: Number(process.env.WEB_PORT || 5173),
    strictPort: true,
    proxy: {
      '/api': { target: apiTarget, changeOrigin: true },
      '/health': { target: apiTarget, changeOrigin: true },
    },
  },
})
