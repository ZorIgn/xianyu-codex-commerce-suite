/**
 * 共享多人扫码登录 - 管理端
 *
 * 功能：
 * 1. 创建共享扫码会话，生成可分享给多个兼职的链接
 * 2. 实时监控所有兼职的扫码状态
 * 3. 查看和管理历史共享会话列表
 *
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  CheckCircle,
  Clock,
  Copy,
  Plus,
  RefreshCw,
  ScanLine,
  Share2,
  Trash2,
  Users,
} from 'lucide-react'
import { useUIStore } from '@/store/uiStore'
import {
  createSharedSession,
  deleteSharedSession,
  getSharedSessionStatus,
  listSharedSessions,
  type SharedScanSessionItem,
  type SharedScanWorker,
} from '@/api/sharedScan'
import { ConfirmModal } from '@/components/common/ConfirmModal'

export function SharedScanManager() {
  const navigate = useNavigate()
  const { addToast } = useUIStore()

  // 会话列表
  const [sessions, setSessions] = useState<SharedScanSessionItem[]>([])
  const [loadingSessions, setLoadingSessions] = useState(false)

  // 当前选中监控的会话
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [workers, setWorkers] = useState<SharedScanWorker[]>([])
  const [activeSessionInfo, setActiveSessionInfo] = useState<SharedScanSessionItem | null>(null)

  // 创建中状态
  const [creating, setCreating] = useState(false)

  // 删除确认
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)

  // 轮询定时器
  const pollTimer = useRef<ReturnType<typeof setInterval> | null>(null)

  // ==================== 数据加载 ====================

  const fetchSessions = useCallback(async () => {
    setLoadingSessions(true)
    try {
      const res = await listSharedSessions()
      if (res.success && res.data) {
        setSessions(res.data.sessions ?? [])
      } else if (!res.success) {
        addToast({ type: 'error', message: res.message || '获取会话列表失败' })
      }
    } catch {
      addToast({ type: 'error', message: '网络错误，请重试' })
    } finally {
      setLoadingSessions(false)
    }
  }, [addToast])

  useEffect(() => {
    fetchSessions()
  }, [fetchSessions])

  // ==================== 创建会话 ====================

  const handleCreate = async () => {
    setCreating(true)
    try {
      const res = await createSharedSession()
      if (res.success && res.data) {
        addToast({ type: 'success', message: '共享会话创建成功' })
        await fetchSessions()
        handleSelectSession(res.data.session_id)
      } else {
        addToast({ type: 'error', message: res.message || '创建失败' })
      }
    } catch {
      addToast({ type: 'error', message: '网络错误，请重试' })
    } finally {
      setCreating(false)
    }
  }

  // ==================== 删除会话 ====================

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return
    try {
      const res = await deleteSharedSession(deleteTarget)
      if (res.success) {
        addToast({ type: 'success', message: '会话已删除' })
        if (activeSessionId === deleteTarget) {
          stopPolling()
          setActiveSessionId(null)
          setWorkers([])
          setActiveSessionInfo(null)
        }
        await fetchSessions()
      } else {
        addToast({ type: 'error', message: res.message || '删除失败' })
      }
    } catch {
      addToast({ type: 'error', message: '网络错误，请重试' })
    } finally {
      setDeleteTarget(null)
    }
  }

  // ==================== 轮询兼职状态 ====================

  const stopPolling = () => {
    if (pollTimer.current) {
      clearInterval(pollTimer.current)
      pollTimer.current = null
    }
  }

  const fetchWorkers = useCallback(async (sessionId: string) => {
    try {
      const res = await getSharedSessionStatus(sessionId)
      if (res.success && res.data) {
        setWorkers(res.data.part_time_workers)
      }
    } catch {
      // 静默失败，不打断轮询
    }
  }, [])

  const handleSelectSession = useCallback((sessionId: string) => {
    stopPolling()
    setActiveSessionId(sessionId)
    setWorkers([])
    fetchWorkers(sessionId)
    pollTimer.current = setInterval(() => {
      fetchWorkers(sessionId)
    }, 3000)
  }, [fetchWorkers])

  useEffect(() => {
    return () => stopPolling()
  }, [])

  // 同步 activeSessionInfo
  useEffect(() => {
    if (activeSessionId) {
      const found = sessions.find(s => s.session_id === activeSessionId) ?? null
      setActiveSessionInfo(found)
    }
  }, [activeSessionId, sessions])

  // ==================== 复制链接 ====================

  const handleCopyUrl = async (url: string) => {
    const displayedUrl = url.trim()
    try {
      await navigator.clipboard.writeText(displayedUrl)
      addToast({ type: 'success', message: '链接已复制到剪贴板' })
      return
    } catch {
      const textArea = document.createElement('textarea')
      textArea.value = displayedUrl
      textArea.setAttribute('readonly', 'readonly')
      textArea.style.position = 'fixed'
      textArea.style.left = '-9999px'
      document.body.appendChild(textArea)
      textArea.focus()
      textArea.select()

      const copied = document.execCommand('copy')
      document.body.removeChild(textArea)

      if (copied) {
        addToast({ type: 'success', message: '链接已复制到剪贴板' })
        return
      }

      addToast({ type: 'error', message: '复制失败，请手动复制界面中的链接' })
    }
  }

  // ==================== 状态徽章 ====================

  const getWorkerBadge = (status: string) => {
    switch (status) {
      case 'qrcode_ready': return <span className="badge-info">等待扫码</span>
      case 'scanning':     return <span className="badge-warning">扫码中</span>
      case 'success':      return <span className="badge-success">登录成功</span>
      case 'failed':       return <span className="badge-danger">登录失败</span>
      default:             return <span className="badge-gray">未知</span>
    }
  }

  const stats = {
    total:   workers.length,
    waiting: workers.filter(w => w.status === 'qrcode_ready').length,
    scanning: workers.filter(w => w.status === 'scanning').length,
    success: workers.filter(w => w.status === 'success').length,
  }

  return (
    <div className="space-y-4">
      {/* 页面标题栏 */}
      <div className="page-header flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/accounts')}
            className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="page-title">兼职登录</h1>
          <p className="page-description">创建共享会话，将链接发给多个兼职人员，各自独立扫码登录闲鱼账号</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={fetchSessions} disabled={loadingSessions} className="btn-ios-secondary">
            <RefreshCw className={`w-4 h-4 ${loadingSessions ? 'animate-spin' : ''}`} />
            刷新
          </button>
          <button onClick={handleCreate} disabled={creating} className="btn-ios-primary">
            <Plus className="w-4 h-4" />
            {creating ? '创建中...' : '新建会话'}
          </button>
        </div>
      </div>

      {/* 主体：左右分栏 */}
      <div className="flex gap-4" style={{ height: 'calc(100vh - 200px)', minHeight: '500px' }}>

        {/* 左侧：会话列表 */}
        <div className="w-72 flex-shrink-0 flex flex-col gap-3">
          <div className="vben-card flex flex-col flex-1 overflow-hidden">
            <div className="vben-card-header flex-shrink-0">
              <h2 className="vben-card-title">
                <Share2 className="w-4 h-4" />
                会话列表
              </h2>
              <span className="badge-primary">{sessions.length}</span>
            </div>

            <div className="flex-1 overflow-y-auto divide-y divide-slate-100 dark:divide-slate-700">
              {sessions.length === 0 && !loadingSessions && (
                <div className="empty-state py-10">
                  <ScanLine className="w-10 h-10 text-slate-300 dark:text-slate-600 mb-3" />
                  <p className="text-sm text-slate-500 dark:text-slate-400">暂无共享会话</p>
                  <p className="text-xs text-slate-400 mt-1">点击「新建会话」开始</p>
                </div>
              )}
              {sessions.map(s => (
                <div
                  key={s.session_id}
                  onClick={() => handleSelectSession(s.session_id)}
                  className={`p-3 cursor-pointer transition-colors ${
                    activeSessionId === s.session_id
                      ? 'bg-blue-50 dark:bg-blue-900/20'
                      : 'hover:bg-slate-50 dark:hover:bg-slate-800/50'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-mono text-slate-500 dark:text-slate-400">
                      {s.session_id.slice(0, 8)}...
                    </span>
                    <div className="flex items-center gap-0.5">
                      <button
                        onClick={e => { e.stopPropagation(); handleCopyUrl(s.share_url) }}
                        title="复制分享链接"
                        className="table-action-btn"
                      >
                        <Copy className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={e => { e.stopPropagation(); setDeleteTarget(s.session_id) }}
                        title="删除会话"
                        className="table-action-btn hover:!text-red-500"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
                    <span className="flex items-center gap-1">
                      <Users className="w-3 h-3" />
                      {s.worker_count} 人
                    </span>
                    <span className="flex items-center gap-1 text-green-600 dark:text-green-400">
                      <CheckCircle className="w-3 h-3" />
                      {s.success_count} 成功
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-slate-400 flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {new Date(s.created_at).toLocaleString('zh-CN')}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 右侧：监控面板 */}
        <div className="flex-1 flex flex-col gap-3 min-w-0">
          {!activeSessionId ? (
            <div className="vben-card flex-1 flex items-center justify-center">
              <div className="empty-state">
                <Users className="w-14 h-14 text-slate-300 dark:text-slate-600 mb-3" />
                <p className="text-base font-medium text-slate-600 dark:text-slate-400">选择或新建一个共享会话</p>
                <p className="text-sm text-slate-400 mt-1">点击左侧会话查看实时监控</p>
              </div>
            </div>
          ) : (
            <>
              {/* 分享链接 */}
              {activeSessionInfo && (
                <div className="vben-card">
                  <div className="vben-card-body">
                    <p className="input-label mb-2 flex items-center gap-1.5">
                      <Share2 className="w-3.5 h-3.5 text-blue-500" />
                      分享链接（发给所有兼职人员）
                    </p>
                    <div className="flex gap-2">
                      <input
                        readOnly
                        value={activeSessionInfo.share_url}
                        className="input-ios font-mono text-xs"
                      />
                      <button
                        onClick={() => handleCopyUrl(activeSessionInfo.share_url)}
                        className="btn-ios-secondary flex-shrink-0"
                      >
                        <Copy className="w-4 h-4" />
                        复制
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* 统计卡片 */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 flex-shrink-0">
                <div className="stat-card">
                  <div className="stat-icon bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300">
                    <Users className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="stat-value">{stats.total}</div>
                    <div className="stat-label">总人数</div>
                  </div>
                </div>
                <div className="stat-card">
                  <div className="stat-icon-primary">
                    <ScanLine className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="stat-value">{stats.waiting}</div>
                    <div className="stat-label">等待扫码</div>
                  </div>
                </div>
                <div className="stat-card">
                  <div className="stat-icon-warning">
                    <RefreshCw className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="stat-value">{stats.scanning}</div>
                    <div className="stat-label">扫码中</div>
                  </div>
                </div>
                <div className="stat-card">
                  <div className="stat-icon-success">
                    <CheckCircle className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="stat-value">{stats.success}</div>
                    <div className="stat-label">登录成功</div>
                  </div>
                </div>
              </div>

              {/* 兼职列表 */}
              <div className="vben-card flex flex-col flex-1 overflow-hidden">
                <div className="vben-card-header flex-shrink-0">
                  <h2 className="vben-card-title">
                    <Users className="w-4 h-4" />
                    实时监控
                  </h2>
                  <div className="flex items-center gap-2">
                    <span className="badge-primary">{workers.length} 人</span>
                    <button
                      onClick={() => fetchWorkers(activeSessionId)}
                      title="手动刷新"
                      className="table-action-btn"
                    >
                      <RefreshCw className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                <div className="flex-1 overflow-auto relative">
                  {workers.length === 0 ? (
                    <div className="empty-state py-12">
                      <Users className="w-10 h-10 text-slate-300 dark:text-slate-600 mb-3" />
                      <p className="text-sm text-slate-500 dark:text-slate-400">暂无兼职加入</p>
                      <p className="text-xs text-slate-400 mt-1">将共享链接发给兼职人员后，这里实时显示</p>
                    </div>
                  ) : (
                    <div className="table-ios-container">
                      <table className="table-ios">
                        <thead className="sticky top-0 bg-white dark:bg-slate-800 z-[1]">
                          <tr>
                            <th>序号</th>
                            <th>状态</th>
                            <th>账号ID（unb）</th>
                            <th>加入时间</th>
                          </tr>
                        </thead>
                        <tbody>
                          {workers.map((w, i) => (
                            <tr key={w.sub_session_id}>
                              <td className="font-mono text-slate-400">#{i + 1}</td>
                              <td>{getWorkerBadge(w.status)}</td>
                              <td className="font-mono">
                                {w.account_id ? (
                                  <span className="flex items-center gap-1 text-green-600 dark:text-green-400">
                                    <CheckCircle className="w-3.5 h-3.5" />
                                    {w.account_id}
                                  </span>
                                ) : (
                                  <span className="text-slate-400">—</span>
                                )}
                              </td>
                              <td className="text-slate-500 dark:text-slate-400">
                                {new Date(w.joined_at * 1000).toLocaleString('zh-CN')}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* 删除确认弹窗 */}
      <ConfirmModal
        isOpen={!!deleteTarget}
        title="删除共享会话"
        message="确定要删除此共享会话吗？该操作将同时清除所有兼职记录，且无法恢复。"
        confirmText="确认删除"
        cancelText="取消"
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
        type="danger"
      />
    </div>
  )
}
