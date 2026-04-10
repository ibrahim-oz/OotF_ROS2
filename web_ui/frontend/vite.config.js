import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

function quietWsProxy(proxy) {
  proxy.on('error', (err, _req, _res) => {
    if (err?.code === 'EPIPE' || err?.code === 'ECONNRESET') {
      return
    }
    console.error('[vite-proxy]', err)
  })
}

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/dsr_description2': 'http://localhost:8000',
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        configure: quietWsProxy,
      },
      '/rosbridge': {
        target: 'ws://localhost:8000',
        ws: true,
        configure: quietWsProxy,
      },
    },
  },
})
