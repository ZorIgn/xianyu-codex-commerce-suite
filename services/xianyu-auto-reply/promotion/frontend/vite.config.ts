/**
 * 推广返佣系统 - Vite构建配置
 *
 * 功能：
 * 1. React插件配置
 * 2. 路径别名 @/ -> src/
 * 3. 开发服务器代理到后端 /api -> localhost:8092
 * 4. 构建输出目录配置
 */
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 9001,
    host: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8092',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
