/**
 * 推广返佣系统 - 认证状态管理
 *
 * 功能：
 * 1. 管理用户token、refreshToken、用户信息
 * 2. 持久化到localStorage
 * 3. 支持hydration检测
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface UserInfo {
  user_id: number
  username: string
  is_admin: boolean
  account_limit?: number | null
}

interface AuthState {
  token: string | null
  refreshToken: string | null
  user: UserInfo | null
  isAuthenticated: boolean
  _hasHydrated: boolean

  setAuth: (token: string, refreshToken: string, user: UserInfo) => void
  clearAuth: () => void
  updateTokens: (token: string, refreshToken: string) => void
  setHasHydrated: (state: boolean) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
      _hasHydrated: false,

      setAuth: (token, refreshToken, user) => {
        localStorage.setItem('auth_token', token)
        localStorage.setItem('refresh_token', refreshToken)
        set({ token, refreshToken, user, isAuthenticated: true })
      },

      clearAuth: () => {
        localStorage.removeItem('auth_token')
        localStorage.removeItem('refresh_token')
        set({ token: null, refreshToken: null, user: null, isAuthenticated: false })
      },

      updateTokens: (token, refreshToken) => {
        localStorage.setItem('auth_token', token)
        localStorage.setItem('refresh_token', refreshToken)
        set({ token, refreshToken })
      },

      setHasHydrated: (state) => {
        set({ _hasHydrated: state })
      },
    }),
    {
      name: 'promotion-auth-storage',
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true)
      },
    }
  )
)
