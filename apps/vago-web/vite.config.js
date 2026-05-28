import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // 所有 /api/v1/** 请求均路由到 Java 单体后端（含 /api/v1/ai/**）。
      // AI 端点由 Java AiController 处理 JWT 鉴权后再转发给 Python vago-ai，
      // 前端不直连 Python，保证安全性。
      '/api/v1': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
})
