import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // AI 对话推理接口直连 Python vago-ai（消除 SSE 代理链路）。
      // 必须列在通用 /api/v1 规则之前，Vite 按顺序匹配，更具体的规则优先。
      '/api/v1/ai/chat': {
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
