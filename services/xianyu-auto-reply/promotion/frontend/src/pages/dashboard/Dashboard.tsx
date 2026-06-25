/**
 * 推广返佣系统 - 仪表盘页面
 *
 * 功能：
 * 1. 显示账号统计概览卡片
 * 2. 管理员额外显示用户数
 * 3. 加载遮罩
 */
import { useEffect, useState } from 'react'
import { Users, UserCheck, UserX, UserPlus } from 'lucide-react'
import { getDashboardStats } from '@/api/dashboard'
import { useAuthStore } from '@/store/authStore'
import { useUIStore } from '@/store/uiStore'
import { getApiErrorMessage } from '@/utils/request'
import { PageLoading } from '@/components/common/Loading'
import type { DashboardStats } from '@/types'

export function Dashboard() {
  const { user } = useAuthStore()
  const { addToast } = useUIStore()
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadStats()
  }, [])

  const loadStats = async () => {
    setLoading(true)
    try {
      const res = await getDashboardStats()
      if (res.success && res.data) {
        setStats(res.data)
      } else {
        addToast({ message: res.message || '获取统计数据失败', type: 'error' })
      }
    } catch (err) {
      addToast({ message: getApiErrorMessage(err), type: 'error' })
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <PageLoading />

  return (
    <div>
      {/* 页面头部 */}
      <div className="page-header">
        <h1 className="page-title">仪表盘</h1>
        <p className="page-description">
          欢迎回来，{user?.username}
          {user?.is_admin ? ' (管理员)' : ''}
        </p>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {/* 总账号数 */}
        <div className="stat-card">
          <div className="stat-icon-primary">
            <Users className="w-5 h-5" />
          </div>
          <div>
            <div className="stat-value">{stats?.total_accounts ?? 0}</div>
            <div className="stat-label">总账号数</div>
          </div>
        </div>

        {/* 启用账号 */}
        <div className="stat-card">
          <div className="stat-icon-success">
            <UserCheck className="w-5 h-5" />
          </div>
          <div>
            <div className="stat-value">{stats?.active_accounts ?? 0}</div>
            <div className="stat-label">启用账号</div>
          </div>
        </div>

        {/* 禁用账号 */}
        <div className="stat-card">
          <div className="stat-icon-warning">
            <UserX className="w-5 h-5" />
          </div>
          <div>
            <div className="stat-value">{stats?.inactive_accounts ?? 0}</div>
            <div className="stat-label">禁用账号</div>
          </div>
        </div>

        {/* 管理员：用户数 */}
        {user?.is_admin && (
          <div className="stat-card">
            <div className="stat-icon-info">
              <UserPlus className="w-5 h-5" />
            </div>
            <div>
              <div className="stat-value">{stats?.total_users ?? 0}</div>
              <div className="stat-label">总用户数</div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
