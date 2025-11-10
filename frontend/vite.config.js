import path from 'node:path'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const rootEnv = loadEnv(mode, path.resolve(__dirname, '..'), '')
  const localEnv = loadEnv(mode, process.cwd(), '')
  const env = { ...rootEnv, ...localEnv }

  const backendHost = env.VITE_BACKEND_HOST || env.APP_HOST || 'localhost'
  const backendPort = env.VITE_BACKEND_PORT || env.APP_PORT || '8000'
  const backendHttpTarget = env.VITE_BACKEND_URL || `http://${backendHost}:${backendPort}`
  const backendWsTarget = env.VITE_BACKEND_WS_URL || backendHttpTarget.replace(/^http/i, 'ws')

  return {
    plugins: [react()],
    base: '/static/',
    build: {
      outDir: 'dist',
      assetsDir: 'static/assets'
    },
    server: {
      proxy: {
        '/api': {
          target: backendHttpTarget,
          changeOrigin: true
        },
        '/ws': {
          target: backendWsTarget,
          ws: true,
          changeOrigin: true
        },
        '/mcp': {
          target: backendHttpTarget,
          changeOrigin: true
        }
      }
    }
  }
})