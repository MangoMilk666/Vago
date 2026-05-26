import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // CRUD 请求 → Java 单体后端
      '/api/v1': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      // AI 请求 → Python FastAPI（如直接从前端调用）
      '/api/v1/ai': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
