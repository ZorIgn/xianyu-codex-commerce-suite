/**
 * 推广返佣系统 - 顶部导航栏组件
 *
 * 功能：
 * 1. 移动端菜单按钮
 * 2. 页面面包屑/标题
 * 3. 用户信息和下拉菜单
 */
import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Menu, User, LogOut, ChevronDown } from 'lucide-react'
import { useUIStore } from '@/store/uiStore'
import { useAuthStore } from '@/store/authStore'
import { cn } from '@/utils/cn'

export function TopNavbar() {
  const navigate = useNavigate()
  const { setSidebarMobileOpen } = useUIStore()
  const { user, clearAuth } = useAuthStore()
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // 点击外部关闭下拉菜单
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleLogout = () => {
    clearAuth()
    navigate('/login')
  }

  return (
    <div className="top-navbar">
      {/* 左侧：移动端菜单按钮 */}
      <div className="flex items-center gap-3">
        <button
          className="lg:hidden p-1.5 rounded-md text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
          onClick={() => setSidebarMobileOpen(true)}
        >
          <Menu className="w-5 h-5" />
        </button>
      </div>

      {/* 右侧：用户信息 */}
      <div className="relative" ref={dropdownRef}>
        <button
          className={cn(
            'flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm',
            'text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700',
            'transition-colors'
          )}
          onClick={() => setDropdownOpen(!dropdownOpen)}
        >
          <div className="w-7 h-7 rounded-full bg-blue-500 flex items-center justify-center">
            <User className="w-4 h-4 text-white" />
          </div>
          <span className="hidden sm:inline">{user?.username || '用户'}</span>
          <ChevronDown className={cn('w-4 h-4 transition-transform', dropdownOpen && 'rotate-180')} />
        </button>

        {/* 下拉菜单 */}
        {dropdownOpen && (
          <div className="absolute right-0 top-full mt-1 w-48 bg-white dark:bg-slate-800 rounded-lg shadow-xl border border-slate-200 dark:border-slate-700 py-1 z-50 animate-fade-in">
            <div className="px-4 py-2 border-b border-slate-100 dark:border-slate-700">
              <p className="text-sm font-medium text-slate-900 dark:text-slate-100">{user?.username}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {user?.is_admin ? '管理员' : '普通用户'}
              </p>
            </div>
            <button
              onClick={handleLogout}
              className="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
            >
              <LogOut className="w-4 h-4" />
              退出登录
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
