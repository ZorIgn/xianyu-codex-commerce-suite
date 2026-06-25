/**
 * 发布规则 - 列表页面
 *
 * 功能：
 * 1. 分页展示当前用户的发布规则
 * 2. 新建/编辑/删除规则
 * 3. 启用/禁用开关
 * 4. 手动执行
 * 5. 后端分页
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { Plus, Pencil, Trash2, Loader2, Play, RefreshCw } from 'lucide-react'
import {
  listPublishRules,
  deletePublishRule,
  togglePublishRule,
  executePublishRule,
  getExecutePublishRuleStatus,
} from '@/api/publishRule'
import type { PublishRule } from '@/api/publishRule'
import { PublishRuleFormModal } from './PublishRuleFormModal'
import { DataTablePagination } from '@/components/common/DataTablePagination'
import { useUIStore } from '@/store/uiStore'
import { useAuthStore } from '@/store/authStore'
import { getApiErrorMessage } from '@/utils/request'

const EXECUTE_STATUS_POLL_INTERVAL = 3000
const EXECUTE_STATUS_POLL_MAX_TIMES = 120

export function PublishRules() {
  const { addToast } = useUIStore()
  const isAdmin = useAuthStore((s) => s.user?.is_admin ?? false)
  const [loading, setLoading] = useState(false)
  const [rules, setRules] = useState<PublishRule[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  /** 弹窗状态 */
  const [showForm, setShowForm] = useState(false)
  const [editRule, setEditRule] = useState<PublishRule | null>(null)

  /** 删除确认状态 */
  const [deletingId, setDeletingId] = useState<number | null>(null)
  /** 执行中 */
  const [executingIds, setExecutingIds] = useState<number[]>([])
  const mountedRef = useRef(true)

  const totalPages = Math.ceil(total / pageSize)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  const setRuleExecuting = useCallback((ruleId: number, executing: boolean) => {
    if (!mountedRef.current) {
      return
    }
    setExecutingIds((prev) => {
      if (executing) {
        return prev.includes(ruleId) ? prev : [...prev, ruleId]
      }
      return prev.filter((id) => id !== ruleId)
    })
  }, [])

  /** 加载列表 */
  const fetchList = useCallback(async (showLoading = true) => {
    if (showLoading && mountedRef.current) {
      setLoading(true)
    }
    try {
      const res = await listPublishRules({ page, page_size: pageSize })
      if (res.success && res.data) {
        setRules(res.data.list)
        setTotal(res.data.total)
      } else {
        addToast({ type: 'error', message: res.message || '查询失败' })
      }
    } catch (err) {
      addToast({ type: 'error', message: getApiErrorMessage(err) })
    } finally {
      if (showLoading && mountedRef.current) {
        setLoading(false)
      }
    }
  }, [page, pageSize, addToast])

  useEffect(() => { fetchList() }, [fetchList])

  /** 新建 */
  const handleCreate = () => {
    setEditRule(null)
    setShowForm(true)
  }

  /** 编辑 */
  const handleEdit = (rule: PublishRule) => {
    setEditRule(rule)
    setShowForm(true)
  }

  /** 删除 */
  const handleDelete = async (ruleId: number) => {
    setDeletingId(ruleId)
    try {
      const res = await deletePublishRule(ruleId)
      if (res.success) {
        addToast({ type: 'success', message: '删除成功' })
        fetchList()
      } else {
        addToast({ type: 'error', message: res.message || '删除失败' })
      }
    } catch (err) {
      addToast({ type: 'error', message: getApiErrorMessage(err) })
    } finally {
      if (mountedRef.current) {
        setDeletingId(null)
      }
    }
  }

  const pollExecuteStatus = useCallback(async (taskId: string) => {
    for (let i = 0; i < EXECUTE_STATUS_POLL_MAX_TIMES; i += 1) {
      if (!mountedRef.current) {
        return
      }

      await new Promise((resolve) => window.setTimeout(resolve, EXECUTE_STATUS_POLL_INTERVAL))
      const res = await getExecutePublishRuleStatus(taskId)
      if (!res.success || !res.data) {
        addToast({ type: 'error', message: res.message || '查询执行状态失败' })
        return
      }

      await fetchList(false)

      if (res.data.status === 'success') {
        addToast({ type: 'success', message: res.data.message || '执行成功' })
        await fetchList()
        return
      }

      if (res.data.status === 'failed') {
        addToast({ type: 'error', message: res.data.message || '执行失败' })
        await fetchList()
        return
      }
    }

    addToast({ type: 'info', message: '规则仍在后台执行，请稍后刷新列表查看结果' })
  }, [addToast, fetchList])

  /** 手动执行 */
  const handleExecute = async (ruleId: number) => {
    setRuleExecuting(ruleId, true)
    try {
      const res = await executePublishRule(ruleId)
      if (!res.success || !res.data) {
        addToast({ type: 'error', message: res.message || '执行失败' })
        return
      }

      if (res.data.status === 'success') {
        addToast({ type: 'success', message: res.data.message || '执行成功' })
        await fetchList()
        return
      }

      if (res.data.status === 'failed') {
        addToast({ type: 'error', message: res.data.message || '执行失败' })
        await fetchList()
        return
      }

      addToast({ type: 'info', message: res.message || '已开始后台执行发布规则' })
      await pollExecuteStatus(res.data.task_id)
    } catch (err) {
      addToast({ type: 'error', message: getApiErrorMessage(err) })
    } finally {
      setRuleExecuting(ruleId, false)
    }
  }

  /** 启用/禁用 */
  const handleToggle = async (rule: PublishRule) => {
    try {
      const res = await togglePublishRule(rule.id, !rule.enabled)
      if (res.success) {
        addToast({ type: 'success', message: res.message || '操作成功' })
        fetchList()
      } else {
        addToast({ type: 'error', message: res.message || '操作失败' })
      }
    } catch (err) {
      addToast({ type: 'error', message: getApiErrorMessage(err) })
    }
  }

  /** 切换页码 */
  const handlePageChange = (newPage: number) => {
    if (newPage >= 1 && newPage <= totalPages) setPage(newPage)
  }

  /** 切换每页条数 */
  const handlePageSizeChange = (size: number) => {
    setPageSize(size)
    setPage(1)
  }

  /** 计算列数（管理员多一列） */
  const colCount = isAdmin ? 10 : 9

  return (
    <div className="space-y-4">
      {/* 顶部操作栏 */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">发布规则</h2>
        <div className="flex items-center gap-2">
          <button className="btn-ios-ghost btn-sm flex items-center gap-1.5" onClick={() => fetchList()}>
            <RefreshCw className="w-4 h-4" />刷新
          </button>
          <button onClick={handleCreate} className="btn-ios-primary flex items-center gap-1.5">
            <Plus className="w-4 h-4" />新建规则
          </button>
        </div>
      </div>

      {/* 表格 */}
      <div className="vben-card overflow-hidden">
        <div className="overflow-x-auto" style={{ maxHeight: 'calc(100vh - 260px)' }}>
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-slate-700/50 sticky top-0 z-10">
              <tr>
                {isAdmin && <th className="px-4 py-3 text-center font-medium w-20">用户ID</th>}
                <th className="px-4 py-3 text-left font-medium">规则名称</th>
                <th className="px-4 py-3 text-left font-medium">闲鱼账号</th>
                <th className="px-4 py-3 text-center font-medium">每日数量</th>
                <th className="px-4 py-3 text-center font-medium">总发布数</th>
                <th className="px-4 py-3 text-center font-medium">今日进度</th>
                <th className="px-4 py-3 text-center font-medium">状态</th>
                <th className="px-4 py-3 text-left font-medium">最后执行</th>
                <th className="px-4 py-3 text-left font-medium">创建时间</th>
                <th className="px-4 py-3 text-center font-medium">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-slate-700">
              {loading ? (
                <tr>
                  <td colSpan={colCount} className="py-16 text-center">
                    <Loader2 className="w-6 h-6 animate-spin mx-auto text-blue-500" />
                    <span className="text-gray-400 text-sm mt-2 block">加载中...</span>
                  </td>
                </tr>
              ) : rules.length === 0 ? (
                <tr>
                  <td colSpan={colCount} className="py-16 text-center text-gray-400">
                    暂无发布规则，点击"新建规则"添加
                  </td>
                </tr>
              ) : (
                rules.map((rule) => (
                  <tr key={rule.id} className="hover:bg-gray-50 dark:hover:bg-slate-700/30">
                    {isAdmin && <td className="px-4 py-3 text-center text-xs text-gray-500">{rule.owner_id}</td>}
                    <td className="px-4 py-3 font-medium max-w-[160px] truncate" title={rule.rule_name}>
                      {rule.rule_name}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs max-w-[140px] truncate" title={rule.account_id}>
                      {rule.account_id}
                    </td>
                    <td className="px-4 py-3 text-center">{rule.daily_count}</td>
                    <td className="px-4 py-3 text-center">{rule.total_published_count}</td>
                    <td className="px-4 py-3 text-center">
                      <span className={`text-xs font-medium ${
                        rule.today_count >= rule.daily_count ? 'text-green-600' : 'text-orange-500'
                      }`}>
                        {rule.today_count}/{rule.daily_count}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <button
                        onClick={() => handleToggle(rule)}
                        className={`relative inline-flex h-5 w-10 items-center rounded-full transition-colors ${
                          rule.enabled ? 'bg-blue-500' : 'bg-gray-300 dark:bg-slate-600'
                        }`}
                      >
                        <span
                          className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                            rule.enabled ? 'translate-x-5' : 'translate-x-0.5'
                          }`}
                        />
                      </button>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-400">{rule.last_run_at || '-'}</td>
                    <td className="px-4 py-3 text-xs text-gray-400">{rule.created_at}</td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-1">
                        <button
                          onClick={() => handleExecute(rule.id)}
                          disabled={executingIds.includes(rule.id)}
                          className="p-1.5 rounded hover:bg-green-50 dark:hover:bg-green-900/30 text-green-600"
                          title="手动执行"
                        >
                          {executingIds.includes(rule.id)
                            ? <Loader2 className="w-4 h-4 animate-spin" />
                            : <Play className="w-4 h-4" />
                          }
                        </button>
                        <button
                          onClick={() => handleEdit(rule)}
                          className="p-1.5 rounded hover:bg-blue-50 dark:hover:bg-blue-900/30 text-blue-500"
                          title="编辑"
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(rule.id)}
                          disabled={deletingId === rule.id}
                          className="p-1.5 rounded hover:bg-red-50 dark:hover:bg-red-900/30 text-red-500"
                          title="删除"
                        >
                          {deletingId === rule.id
                            ? <Loader2 className="w-4 h-4 animate-spin" />
                            : <Trash2 className="w-4 h-4" />
                          }
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* 分页 */}
      <DataTablePagination
        total={total}
        page={page}
        totalPages={totalPages || 1}
        pageSize={pageSize}
        loading={loading}
        onPageChange={handlePageChange}
        onPageSizeChange={handlePageSizeChange}
      />

      {/* 新建/编辑弹窗 */}
      {showForm && (
        <PublishRuleFormModal
          rule={editRule}
          onClose={() => setShowForm(false)}
          onSaved={fetchList}
        />
      )}
    </div>
  )
}
