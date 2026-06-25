/**
 * 推广返佣系统 - 多标签栏组件
 *
 * 功能：
 * 1. 显示已打开的菜单标签
 * 2. 支持切换和关闭标签
 * 3. 同步路由
 */
import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { X, Home } from 'lucide-react'
import { getMenuLabelByPath } from '@/config/navigation'
import { cn } from '@/utils/cn'

interface Tab {
  path: string
  label: string
}

export function TabsBar() {
  const navigate = useNavigate()
  const location = useLocation()
  const [tabs, setTabs] = useState<Tab[]>([{ path: '/dashboard', label: '仪表盘' }])

  /** 路由变化时添加标签 */
  useEffect(() => {
    const currentPath = location.pathname
    // 不为login页面添加tab
    if (currentPath === '/login' || currentPath === '/') return

    setTabs((prev) => {
      if (prev.some((t) => t.path === currentPath)) return prev
      const label = getMenuLabelByPath(currentPath)
      return [...prev, { path: currentPath, label }]
    })
  }, [location.pathname])

  /** 切换标签 */
  const handleTabClick = useCallback(
    (path: string) => {
      navigate(path)
    },
    [navigate]
  )

  /** 关闭标签 */
  const handleCloseTab = useCallback(
    (path: string, e: React.MouseEvent) => {
      e.stopPropagation()
      // 不允许关闭最后一个标签和仪表盘
      if (path === '/dashboard' || tabs.length <= 1) return

      setTabs((prev) => {
        const newTabs = prev.filter((t) => t.path !== path)
        // 如果关闭的是当前标签，跳到最后一个
        if (location.pathname === path && newTabs.length > 0) {
          navigate(newTabs[newTabs.length - 1].path)
        }
        return newTabs
      })
    },
    [tabs, location.pathname, navigate]
  )

  return (
    <div className="tabs-bar scrollbar-hide">
      {tabs.map((tab) => {
        const isActive = location.pathname === tab.path
        const isHome = tab.path === '/dashboard'
        return (
          <div
            key={tab.path}
            className={cn(isActive ? 'tab-item-active' : 'tab-item')}
            onClick={() => handleTabClick(tab.path)}
          >
            {isHome && <Home className="w-3.5 h-3.5" />}
            <span>{tab.label}</span>
            {!isHome && (
              <button className="tab-close" onClick={(e) => handleCloseTab(tab.path, e)}>
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        )
      })}
    </div>
  )
}
