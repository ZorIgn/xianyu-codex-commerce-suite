/**
 * 推广返佣系统 - 主布局组件
 *
 * 功能：
 * 1. 左侧侧边栏 + 右侧内容区
 * 2. 顶部导航栏 + 多标签栏
 * 3. 响应式：侧边栏收缩/移动端抽屉
 */
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { TopNavbar } from './TopNavbar'
import { TabsBar } from './TabsBar'
import { useUIStore } from '@/store/uiStore'
import { cn } from '@/utils/cn'

export function MainLayout() {
  const { sidebarCollapsed } = useUIStore()

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 transition-colors">
      {/* 侧边栏 */}
      <Sidebar />

      {/* 主内容区 */}
      <div
        className={cn(
          'transition-all duration-200',
          'lg:ml-60',
          sidebarCollapsed && 'lg:ml-16'
        )}
      >
        {/* 顶部导航栏 */}
        <TopNavbar />

        {/* 多标签栏 */}
        <TabsBar />

        {/* 页面内容 */}
        <main className="p-3 sm:p-4 lg:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
