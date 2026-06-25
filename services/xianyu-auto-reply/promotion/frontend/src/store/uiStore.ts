/**
 * 推广返佣系统 - UI状态管理
 *
 * 功能：
 * 1. 侧边栏收缩/展开状态
 * 2. 移动端侧边栏开关
 * 3. 全局加载状态
 * 4. Toast消息管理
 */
import { create } from 'zustand'

interface Toast {
  id: string
  message: string
  type: 'success' | 'error' | 'warning' | 'info'
  duration?: number
}

interface UIState {
  sidebarCollapsed: boolean
  sidebarMobileOpen: boolean
  loading: boolean
  toasts: Toast[]
  toggleSidebar: () => void
  setSidebarCollapsed: (collapsed: boolean) => void
  setSidebarMobileOpen: (open: boolean) => void
  setLoading: (loading: boolean) => void
  addToast: (toast: Omit<Toast, 'id'>) => void
  removeToast: (id: string) => void
}

export const useUIStore = create<UIState>((set) => ({
  sidebarCollapsed: false,
  sidebarMobileOpen: false,
  loading: false,
  toasts: [],

  toggleSidebar: () => {
    set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed }))
  },

  setSidebarCollapsed: (collapsed) => {
    set({ sidebarCollapsed: collapsed })
  },

  setSidebarMobileOpen: (open) => {
    set({ sidebarMobileOpen: open })
  },

  setLoading: (loading) => {
    set({ loading })
  },

  addToast: (toast) => {
    const id = Math.random().toString(36).substr(2, 9)
    set((state) => ({
      toasts: [...state.toasts, { ...toast, id }],
    }))

    // 自动移除 toast
    const duration = toast.duration ?? 3000
    setTimeout(() => {
      set((state) => ({
        toasts: state.toasts.filter((t) => t.id !== id),
      }))
    }, duration)
  },

  removeToast: (id) => {
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    }))
  },
}))
