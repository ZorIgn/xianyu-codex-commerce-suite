/**
 * 推广返佣系统 - 根路由组件
 *
 * 功能：
 * 1. 路由配置（Login、MainLayout嵌套Dashboard/Accounts）
 * 2. 认证守卫
 * 3. 全局Toast
 */
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { MainLayout } from '@/components/layout/MainLayout'
import { Toast } from '@/components/common/Toast'
import { Login } from '@/pages/auth/Login'
import { Dashboard } from '@/pages/dashboard/Dashboard'
import { Accounts } from '@/pages/accounts/Accounts'
import { ProductSearch } from '@/pages/taobaoAlliance/ProductSearch'
import { ProductRules } from '@/pages/taobaoAlliance/ProductRules'
import { Materials } from '@/pages/taobaoAlliance/Materials'
import { PublishRules } from '@/pages/taobaoAlliance/PublishRules'
import { DeleteRules } from '@/pages/taobaoAlliance/DeleteRules'
import { useAuthStore } from '@/store/authStore'

/** 认证守卫：未登录时跳转登录页 */
function RequireAuth({ children }: { children: JSX.Element }) {
  const { isAuthenticated, _hasHydrated } = useAuthStore()
  if (!_hasHydrated) return null
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return children
}

/** 已登录时重定向到仪表盘 */
function RedirectIfAuth({ children }: { children: JSX.Element }) {
  const { isAuthenticated, _hasHydrated } = useAuthStore()
  if (!_hasHydrated) return null
  if (isAuthenticated) return <Navigate to="/dashboard" replace />
  return children
}

export default function App() {
  return (
    <BrowserRouter>
      {/* 全局Toast */}
      <Toast />

      <Routes>
        {/* 登录页 */}
        <Route
          path="/login"
          element={
            <RedirectIfAuth>
              <Login />
            </RedirectIfAuth>
          }
        />

        {/* 主布局（需认证） */}
        <Route
          path="/"
          element={
            <RequireAuth>
              <MainLayout />
            </RequireAuth>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="accounts" element={<Accounts />} />
          <Route path="taobao-alliance/product-search" element={<ProductSearch />} />
          <Route path="taobao-alliance/product-rules" element={<ProductRules />} />
          <Route path="taobao-alliance/materials" element={<Materials />} />
          <Route path="taobao-alliance/publish-rules" element={<PublishRules />} />
          <Route path="taobao-alliance/delete-rules" element={<DeleteRules />} />
        </Route>

        {/* 404 回退 */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
