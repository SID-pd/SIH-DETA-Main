import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      'motion/react': 'framer-motion'
    }
  },
  server: {
    port: 5173,
    host: true,
    allowedHosts: [
      'doorpost-smashing-regime.ngrok-free.dev',
      '.ngrok-free.dev',
      '.ngrok.io',
      '.ngrok-free.app',
      'localhost',
      '127.0.0.1'
    ],
    proxy: {
      // The frontend talks ONLY to our own API. The previous config proxied
      // api.apimitra.in directly from the browser, which meant the "live" path
      // existed only in dev (no proxy in a production build) and the API key sat in
      // localStorage. Both are gone: keys live in the rail-gateway, server-side.
      '/v1': {
        target: process.env.VITE_API_TARGET || 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
    },
  }
})
