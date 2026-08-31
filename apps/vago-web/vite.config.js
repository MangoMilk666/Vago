import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // AI 对话推理接口直连 Python vago-ai（消除 SSE 代理链路）。
      // Vite 使用前缀匹配：/api/v1/ai/chat 会自动匹配 /api/v1/ai/chat/stream 等子路径。
      // Vite 按规则长度降序排序（长规则优先），因此本规则优先于下方的 /api/v1。
      '/api/v1/ai/chat': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // Phase 3/4 交界：AI 结构化计划保存已迁移到 FastAPI travel domain。
      '/api/v1/ai/plans': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // Phase 2：用户认证与个人资料已迁移到 FastAPI，保留 /api/v1/user 路径兼容前端 client。
      '/api/v1/user': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // Phase 3：Trip / Plan / Itinerary 已迁移到 FastAPI；Guides / Collections 暂留 Java。
      '/api/v1/travel/trips': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/api/v1/travel/plans': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // 其余所有 API（含 /api/v1/ai/plans/save-* 等业务逻辑接口）走 Java 单体
      '/api/v1': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
})
