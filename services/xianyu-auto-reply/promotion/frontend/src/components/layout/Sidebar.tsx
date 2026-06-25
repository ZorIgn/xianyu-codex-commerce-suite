/**
 * 推广返佣系统 - 侧边栏导航组件
 *
 * 功能：
 * 1. 主导航菜单渲染（PC端收缩/展开、移动端抽屉）
 * 2. 管理员专属菜单
 * 3. 子菜单展开/收缩
 * 4. 暗黑模式切换
 * 5. 响应式设计
 */
import { useNavigate, useLocation } from 'react-router-dom'
import { Menu, X, Moon, Sun, ChevronLeft, ChevronDown } from 'lucide-react'
import { useUIStore } from '@/store/uiStore'
import { useAuthStore } from '@/store/authStore'
import { mainNavItems, adminNavItems, type NavItem } from '@/config/navigation'
import { cn } from '@/utils/cn'
import { useEffect, useState } from 'react'

export function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const { sidebarCollapsed, sidebarMobileOpen, toggleSidebar, setSidebarMobileOpen } = useUIStore()
  const { user } = useAuthStore()
  const [isDark, setIsDark] = useState(false)
  const [expandedMenus, setExpandedMenus] = useState<Set<string>>(new Set())

  useEffect(() => {
    setIsDark(document.documentElement.classList.contains('dark'))
  }, [])

  /** 自动展开当前路径所在的父菜单 */
  useEffect(() => {
    const allItems = [...mainNavItems, ...adminNavItems]
    for (const item of allItems) {
      if (item.children) {
        const hasActiveChild = item.children.some((c) => location.pathname.startsWith(c.path))
        if (hasActiveChild) {
          setExpandedMenus((prev) => new Set(prev).add(item.key))
        }
      }
    }
  }, [location.pathname])

  /** 切换暗黑模式 */
  const toggleDarkMode = () => {
    const newDark = !isDark
    setIsDark(newDark)
    if (newDark) {
      document.documentElement.classList.add('dark')
      localStorage.setItem('theme', 'dark')
    } else {
      document.documentElement.classList.remove('dark')
      localStorage.setItem('theme', 'light')
    }
  }

  /** 导航到某路由并关闭移动端侧边栏 */
  const handleNavigate = (path: string) => {
    navigate(path)
    setSidebarMobileOpen(false)
  }

  /** 切换子菜单展开/收缩 */
  const toggleSubMenu = (key: string) => {
    setExpandedMenus((prev) => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }

  const isExpanded = !sidebarCollapsed || sidebarMobileOpen

  /** 渲染单个菜单项（含子菜单支持） */
  const renderMenuItem = (item: NavItem) => {
    if (item.adminOnly && !user?.is_admin) return null
    const Icon = item.icon
    const hasChildren = item.children && item.children.length > 0
    const isParentActive = location.pathname.startsWith(item.path)
    const isMenuExpanded = expandedMenus.has(item.key)

    // 有子菜单：点击展开/收缩
    if (hasChildren) {
      return (
        <div key={item.key}>
          <button
            onClick={() => {
              if (isExpanded) {
                toggleSubMenu(item.key)
              } else {
                // 收缩态点击：先展开侧边栏再展开子菜单
                toggleSidebar()
                setExpandedMenus((prev) => new Set(prev).add(item.key))
              }
            }}
            className={cn(
              'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 border border-transparent',
              isParentActive
                ? 'bg-slate-800 text-white shadow-[0_10px_24px_rgba(15,23,42,0.22)] border-slate-700/80'
                : 'text-slate-300 hover:bg-slate-800/80 hover:text-white',
              !isExpanded && 'justify-center px-2'
            )}
            title={!isExpanded ? item.label : undefined}
          >
            <Icon className="w-5 h-5 flex-shrink-0" />
            {isExpanded && (
              <>
                <span className="flex-1 text-left">{item.label}</span>
                <ChevronDown
                  className={cn(
                    'w-4 h-4 transition-transform duration-200',
                    isMenuExpanded && 'rotate-180'
                  )}
                />
              </>
            )}
          </button>
          {/* 子菜单列表 */}
          {isExpanded && isMenuExpanded && item.children && (
            <div className="mt-1.5 ml-3 space-y-1 border-l border-slate-700/70 pl-3">
              {item.children.map((child) => {
                const ChildIcon = child.icon
                const isChildActive = location.pathname.startsWith(child.path)
                return (
                  <button
                    key={child.key}
                    onClick={() => handleNavigate(child.path)}
                    className={cn(
                      'w-full flex items-center gap-2.5 pl-3.5 pr-3 py-2 rounded-xl text-sm transition-all duration-200 border border-transparent',
                      isChildActive
                        ? 'bg-gradient-to-r from-blue-500/20 to-cyan-500/10 text-blue-100 border-blue-400/20 shadow-[0_10px_20px_rgba(15,23,42,0.2)]'
                        : 'text-slate-400 hover:bg-slate-800/80 hover:text-white'
                    )}
                  >
                    <ChildIcon className="w-4 h-4 flex-shrink-0" />
                    <span>{child.label}</span>
                  </button>
                )
              })}
            </div>
          )}
        </div>
      )
    }

    // 无子菜单：直接导航
    return (
      <button
        key={item.key}
        onClick={() => handleNavigate(item.path)}
        className={cn(
          'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 border border-transparent',
          isParentActive
            ? 'bg-gradient-to-r from-blue-500/20 to-cyan-500/10 text-white border-blue-400/20 shadow-[0_10px_24px_rgba(15,23,42,0.22)]'
            : 'text-slate-300 hover:bg-slate-800/80 hover:text-white',
          !isExpanded && 'justify-center px-2'
        )}
        title={!isExpanded ? item.label : undefined}
      >
        <Icon className="w-5 h-5 flex-shrink-0" />
        {isExpanded && <span>{item.label}</span>}
      </button>
    )
  }

  /** 渲染菜单项列表 */
  const renderMenuItems = (items: NavItem[]) => items.map(renderMenuItem)

  /** 侧边栏内容 */
  const sidebarContent = (
    <div className="flex flex-col h-full">
      {/* Logo区 */}
      <div className="h-14 flex items-center justify-between px-4 border-b border-slate-700/60">
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-cyan-400 text-sm font-bold text-white shadow-[0_8px_20px_rgba(59,130,246,0.35)]">推</div>
          {(!sidebarCollapsed || sidebarMobileOpen) && (
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold tracking-wide text-white">推广返佣</div>
              <div className="truncate text-[11px] text-slate-400">素材 · 规则 · 账号</div>
            </div>
          )}
        </div>
        {/* 移动端关闭按钮 */}
        <button
          className="lg:hidden p-1 text-slate-400 hover:text-white rounded-md transition-colors"
          onClick={() => setSidebarMobileOpen(false)}
        >
          <X className="w-5 h-5" />
        </button>
        {/* PC端收缩按钮 */}
        <button
          className="hidden lg:flex p-1 text-slate-400 hover:text-white rounded-md transition-colors"
          onClick={toggleSidebar}
        >
          <ChevronLeft className={cn('w-5 h-5 transition-transform', sidebarCollapsed && 'rotate-180')} />
        </button>
      </div>

      {/* 主菜单 */}
      <nav className="flex-1 overflow-y-auto sidebar-scrollbar px-3 py-3 space-y-1">
        {renderMenuItems(mainNavItems)}

        {/* 管理员菜单 */}
        {user?.is_admin && adminNavItems.length > 0 && (
          <>
            <div className="mt-4 mb-2 px-3 text-xs font-semibold text-slate-500 uppercase">
              {(!sidebarCollapsed || sidebarMobileOpen) ? '管理' : '—'}
            </div>
            {renderMenuItems(adminNavItems)}
          </>
        )}
      </nav>

      {/* 底部操作 */}
      <div className="border-t border-slate-700/60 p-3 space-y-1">
        {/* 暗黑模式切换 */}
        <button
          onClick={toggleDarkMode}
          className={cn(
            'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-slate-300 hover:bg-slate-700/60 hover:text-white transition-all',
            sidebarCollapsed && !sidebarMobileOpen && 'justify-center px-2'
          )}
          title={isDark ? '切换亮色' : '切换暗色'}
        >
          {isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          {(!sidebarCollapsed || sidebarMobileOpen) && <span>{isDark ? '亮色模式' : '暗色模式'}</span>}
        </button>
      </div>
    </div>
  )

  return (
    <>
      {/* PC端侧边栏 */}
      <aside
        className={cn(
          'hidden lg:flex flex-col fixed left-0 top-0 bottom-0 bg-slate-900 z-40 transition-all duration-200',
          sidebarCollapsed ? 'w-16' : 'w-60'
        )}
      >
        {sidebarContent}
      </aside>

      {/* 移动端遮罩 */}
      {sidebarMobileOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black/50 z-40"
          onClick={() => setSidebarMobileOpen(false)}
        />
      )}

      {/* 移动端侧边栏 */}
      <aside
        className={cn(
          'lg:hidden fixed left-0 top-0 bottom-0 w-64 bg-slate-900 z-50 transition-transform duration-200',
          sidebarMobileOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {sidebarContent}
      </aside>
    </>
  )
}
