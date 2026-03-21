import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Docker 里指向 compose 服务名 backend；本机开发默认连本机 8000
const backendTarget = process.env.VITE_BACKEND_PROXY || 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      // 浏览器只访问同源 /api/*，由 Vite 转发到 FastAPI，避免跨域
      '/api': {
        target: backendTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
