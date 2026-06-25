/**
 * 推广返佣系统 - 前端入口
 *
 * 功能：
 * 1. 挂载React应用到DOM
 * 2. 初始化暗黑模式
 * 3. 从后端获取主系统的主题颜色和字体设置并应用
 */
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles/globals.css'
import './styles/theme.css'
import { applyThemeSettings, initializeThemeMode } from './utils/theme'
import request from './utils/request'

// 初始化暗黑/亮色模式
initializeThemeMode()

// 从后端获取主题设置并应用（异步，不阻塞渲染）
const loadAndApplyTheme = async () => {
  try {
    const response = await request.get('/api/v1/settings/theme')
    if (response.data?.success && response.data?.data) {
      applyThemeSettings(response.data.data)
    }
  } catch {
    // 主题加载失败不影响页面，使用CSS中的默认值
  }
}
loadAndApplyTheme()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
