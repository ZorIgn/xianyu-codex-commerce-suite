/**
 * 素材库 - 列表页面
 *
 * 功能：
 * 1. 分页展示素材列表
 * 2. 关键词搜索
 * 3. 编辑/删除素材
 * 4. 复制淘口令/推广链接
 * 5. 后端分页
 */
import { useState, useEffect, useCallback } from 'react'
import { Search, Pencil, Trash2, Loader2, Copy, ExternalLink, Eye, RefreshCw, Package } from 'lucide-react'
import { listMaterials, deleteMaterial, batchDeleteMaterials } from '@/api/material'
import type { Material } from '@/api/material'
import { listXYAccounts } from '@/api/publishRule'
import type { XYAccountOption } from '@/api/publishRule'
import { MaterialEditModal } from './MaterialEditModal'
import { MaterialDetailModal } from './MaterialDetailModal'
import { DataTablePagination } from '@/components/common/DataTablePagination'
import { useUIStore } from '@/store/uiStore'
import { useAuthStore } from '@/store/authStore'

const publishStatusMap: Record<Material['publish_status'], { text: string; className: string }> = {
  unpublished: {
    text: '未发布',
    className: 'bg-gray-100 text-gray-500 dark:bg-slate-700 dark:text-gray-400',
  },
  published: {
    text: '已发布',
    className: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  },
  failed: {
    text: '发布失败',
    className: 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400',
  },
}

type PublishStatusFilter = '' | Material['publish_status']

export function Materials() {
  const { addToast } = useUIStore()
  const isAdmin = useAuthStore((s) => s.user?.is_admin ?? false)
  const [loading, setLoading] = useState(false)
  const [materials, setMaterials] = useState<Material[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [keyword, setKeyword] = useState('')
  const [searchKeyword, setSearchKeyword] = useState('')
  const [accounts, setAccounts] = useState<XYAccountOption[]>([])
  const [accountFilter, setAccountFilter] = useState('')
  const [publishedFilter, setPublishedFilter] = useState<PublishStatusFilter>('')

  /** 弹窗状态 */
  const [editMaterial, setEditMaterial] = useState<Material | null>(null)
  const [viewMaterial, setViewMaterial] = useState<Material | null>(null)
  /** 删除中 */
  const [deletingId, setDeletingId] = useState<number | null>(null)
  /** 勾选 */
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [batchDeleting, setBatchDeleting] = useState(false)

  const totalPages = Math.ceil(total / pageSize)
  const hasActiveFilters = Boolean(keyword.trim() || searchKeyword || accountFilter || publishedFilter)
  const accountNameMap = new Map(accounts.map((account) => [account.account_id, account.display_name]))
  const currentPagePublishedCount = materials.filter((item) => item.publish_status === 'published').length
  const currentPageFailedCount = materials.filter((item) => item.publish_status === 'failed').length

  const fetchAccounts = useCallback(async () => {
    try {
      const res = await listXYAccounts()
      if (res.success && res.data) {
        setAccounts(res.data)
      } else {
        addToast({ type: 'error', message: res.message || '加载闲鱼账号失败' })
      }
    } catch {
      addToast({ type: 'error', message: '加载闲鱼账号失败' })
    }
  }, [addToast])

  /** 加载列表 */
  const fetchList = useCallback(async () => {
    setLoading(true)
    try {
      const publishStatus = publishedFilter ? publishedFilter : undefined
      const res = await listMaterials({
        page,
        page_size: pageSize,
        keyword: searchKeyword,
        account_id: accountFilter || undefined,
        publish_status: publishStatus,
      })
      if (res.success && res.data) {
        setMaterials(res.data.list)
        setTotal(res.data.total)
      } else {
        addToast({ type: 'error', message: res.message || '查询失败' })
      }
    } catch {
      addToast({ type: 'error', message: '查询请求失败' })
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, searchKeyword, accountFilter, publishedFilter, addToast])

  useEffect(() => { fetchList() }, [fetchList])
  useEffect(() => { fetchAccounts() }, [fetchAccounts])

  /** 搜索 */
  const handleSearch = () => {
    const nextKeyword = keyword.trim()
    if (page === 1 && nextKeyword === searchKeyword) {
      fetchList()
      return
    }
    setSearchKeyword(nextKeyword)
    setPage(1)
  }

  /** 删除 */
  const handleDelete = async (id: number) => {
    setDeletingId(id)
    try {
      const res = await deleteMaterial(id)
      if (res.success) {
        addToast({ type: 'success', message: '删除成功' })
        fetchList()
      } else {
        addToast({ type: 'error', message: res.message || '删除失败' })
      }
    } catch {
      addToast({ type: 'error', message: '删除请求失败' })
    } finally {
      setDeletingId(null)
    }
  }

  /** 切换全选 */
  const handleToggleAll = () => {
    if (selectedIds.size === materials.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(materials.map((m) => m.id)))
    }
  }

  /** 切换单选 */
  const handleToggleOne = (id: number) => {
    const next = new Set(selectedIds)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setSelectedIds(next)
  }

  /** 批量删除 */
  const handleBatchDelete = async () => {
    if (selectedIds.size === 0) { addToast({ type: 'warning', message: '请先勾选要删除的素材' }); return }
    setBatchDeleting(true)
    try {
      const res = await batchDeleteMaterials(Array.from(selectedIds))
      if (res.success) {
        addToast({ type: 'success', message: res.message || '批量删除成功' })
        setSelectedIds(new Set())
        fetchList()
      } else {
        addToast({ type: 'error', message: res.message || '批量删除失败' })
      }
    } catch {
      addToast({ type: 'error', message: '批量删除请求失败' })
    } finally {
      setBatchDeleting(false)
    }
  }

  /** 复制文本 */
  const handleCopy = async (text: string, label: string) => {
    if (!text) { addToast({ type: 'warning', message: `暂无${label}` }); return }
    try {
      await navigator.clipboard.writeText(text)
      addToast({ type: 'success', message: `${label}已复制` })
    } catch {
      addToast({ type: 'error', message: '复制失败' })
    }
  }

  /** 切换页码 */
  const handlePageChange = (p: number) => { if (p >= 1 && p <= totalPages) setPage(p) }

  /** 切换每页条数 */
  const handlePageSizeChange = (s: number) => { setPageSize(s); setPage(1) }

  const handleResetFilters = () => {
    setKeyword('')
    setSearchKeyword('')
    setAccountFilter('')
    setPublishedFilter('')
    setPage(1)
  }

  return (
    <div className="space-y-4">
      {/* 顶部搜索栏 */}
      <div className="page-header flex-between flex-wrap gap-3">
        <div>
          <h1 className="page-title">素材库</h1>
          <p className="page-description">统一查看淘宝联盟素材的价格、佣金、发布状态与推广信息</p>
        </div>
        <button onClick={fetchList} disabled={loading} className="btn-ios-secondary">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />刷新
        </button>
      </div>

      {/* 批量操作栏 */}
      <div className="vben-card flex flex-col overflow-hidden" style={{ height: 'calc(100vh - 220px)', minHeight: '420px' }}>
        <div className="vben-card-header flex-wrap gap-3">
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="vben-card-title"><Package className="w-4 h-4" />素材列表</h2>
            <span className="badge-primary">共 {total} 条</span>
            <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400">
              当前页已发布 {currentPagePublishedCount} 条
            </span>
            {currentPageFailedCount > 0 && <span className="inline-flex items-center rounded-full border border-red-200 bg-red-50 px-3 py-1 text-xs text-red-500 dark:border-red-900/60 dark:bg-red-900/20 dark:text-red-300">发布失败 {currentPageFailedCount} 条</span>}
          </div>
          <span className="text-xs text-slate-400">后端分页 · 默认每页 20 条</span>
        </div>

        <div className="flex-shrink-0 border-b border-slate-100 bg-slate-50/70 px-5 py-4 dark:border-slate-700 dark:bg-slate-800/50">
          <div className="grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,1.5fr)_180px_160px_auto]">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="搜索商品标题、商品ID、描述"
                className="input-ios pl-9"
              />
            </div>
            <select
              value={accountFilter}
              onChange={(e) => { setAccountFilter(e.target.value); setPage(1) }}
              className="input-ios"
            >
              <option value="">全部账号</option>
              {accounts.map((account) => <option key={account.account_id} value={account.account_id}>{account.display_name}</option>)}
            </select>
            <select
              value={publishedFilter}
              onChange={(e) => { setPublishedFilter((e.target.value || '') as PublishStatusFilter); setPage(1) }}
              className="input-ios"
            >
              <option value="">全部状态</option>
              <option value="unpublished">未发布</option>
              <option value="published">已发布</option>
              <option value="failed">发布失败</option>
            </select>
            <div className="flex flex-wrap items-center gap-2 xl:justify-end">
              <button onClick={handleSearch} className="btn-ios-primary flex items-center gap-1.5">
                <Search className="w-4 h-4" />搜索
              </button>
              {hasActiveFilters && (
                <button onClick={handleResetFilters} className="btn-ios-secondary">
                  重置
                </button>
              )}
            </div>
          </div>

          {selectedIds.size > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-3 rounded-xl border border-blue-100 bg-blue-50/80 px-4 py-3 dark:border-blue-900/50 dark:bg-blue-900/20">
              <span className="text-sm font-medium text-blue-600 dark:text-blue-300">已选择 {selectedIds.size} 项</span>
              <button onClick={handleBatchDelete} disabled={batchDeleting} className="btn-ios-secondary btn-sm text-red-500 border-red-200 hover:bg-red-50 dark:hover:bg-red-900/30 flex items-center gap-1">
                {batchDeleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}批量删除
              </button>
              <button onClick={() => setSelectedIds(new Set())} className="btn-ios-secondary btn-sm text-gray-500">取消选择</button>
            </div>
          )}
        </div>

        {/* 表格 */}
        <div className="flex-1 overflow-auto">
          <table className="table-ios min-w-[1800px]">
            <thead className="sticky top-0 z-10 bg-slate-50/95 backdrop-blur dark:bg-slate-800/95">
              <tr>
                <th className="w-10 whitespace-nowrap text-center">
                  <input
                    type="checkbox"
                    checked={materials.length > 0 && selectedIds.size === materials.length}
                    onChange={handleToggleAll}
                    className="w-4 h-4 rounded border-gray-300 text-blue-500"
                  />
                </th>
                <th className="w-20 whitespace-nowrap">图片</th>
                <th className="w-44 whitespace-nowrap">账号信息</th>
                <th className="min-w-[320px] whitespace-nowrap">商品信息</th>
                <th className="w-48 whitespace-nowrap text-center">价格信息</th>
                <th className="w-36 whitespace-nowrap text-center">佣金信息</th>
                <th className="w-44 whitespace-nowrap">店铺信息</th>
                <th className="w-56 whitespace-nowrap">发布信息</th>
                <th className="w-56 whitespace-nowrap">推广信息</th>
                <th className="w-44 whitespace-nowrap">创建时间</th>
                <th className="sticky right-0 z-20 w-32 whitespace-nowrap bg-slate-50/95 text-center backdrop-blur dark:bg-slate-800/95">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-slate-700">
              {loading ? (
                <tr><td colSpan={11} className="py-16 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-blue-500" /><span className="text-gray-400 text-sm mt-2 block">加载中...</span></td></tr>
              ) : materials.length === 0 ? (
                <tr><td colSpan={11} className="py-16 text-center text-gray-400">暂无素材，启用选品规则后系统会自动采集</td></tr>
              ) : (
                materials.map((m) => (
                  <tr key={m.id} className={`hover:bg-gray-50 dark:hover:bg-slate-700/30 ${selectedIds.has(m.id) ? 'bg-blue-50/50 dark:bg-blue-900/10' : ''}`}>
                    <td className="text-center">
                      <input
                        type="checkbox"
                        checked={selectedIds.has(m.id)}
                        onChange={() => handleToggleOne(m.id)}
                        className="w-4 h-4 rounded border-gray-300 text-blue-500"
                      />
                    </td>
                    {/* 图片 */}
                    <td>
                      {m.images && m.images.length > 0 ? (
                        <img
                          src={m.images[0]}
                          alt=""
                          className="h-14 w-14 rounded-xl border border-slate-200 object-cover shadow-sm dark:border-slate-700"
                          onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
                        />
                      ) : (
                        <div className="flex h-14 w-14 items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-xs text-slate-400 dark:border-slate-700 dark:bg-slate-800">无图</div>
                      )}
                    </td>
                    <td className="align-top">
                      <div className="min-w-0 space-y-1">
                        <div className="truncate text-sm font-medium text-slate-800 dark:text-slate-100" title={accountNameMap.get(m.account_id) || m.account_id || '-'}>{accountNameMap.get(m.account_id) || m.account_id || '-'}</div>
                        <div className="truncate font-mono text-xs text-slate-400" title={m.account_id || '-'}>{m.account_id || '-'}</div>
                        {isAdmin && <div className="text-xs text-slate-400">用户ID：{m.owner_id}</div>}
                      </div>
                    </td>
                    {/* 标题 */}
                    <td className="align-top">
                      <div className="space-y-2">
                        <button onClick={() => setViewMaterial(m)} className="line-clamp-2 text-left text-sm font-semibold leading-6 text-slate-800 transition-colors hover:text-blue-600 dark:text-slate-100 dark:hover:text-blue-300" title={m.title}>{m.title}</button>
                        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
                          <span className="inline-flex items-center rounded-md bg-slate-100 px-2 py-1 font-mono text-slate-500 dark:bg-slate-800 dark:text-slate-300">商品ID：{m.item_id || '-'}</span>
                        </div>
                      </div>
                    </td>
                    <td className="align-top text-center">
                      <div className="space-y-1.5 text-xs">
                        <div><span className="text-slate-400">售价</span><span className="ml-2 font-semibold text-red-500">¥{m.price}</span></div>
                        <div><span className="text-slate-400">原价</span><span className="ml-2 text-slate-500">{m.original_price ? `¥${m.original_price}` : '-'}</span></div>
                        <div><span className="text-slate-400">到手</span><span className="ml-2 font-semibold text-emerald-600">{m.promotion_price ? `¥${m.promotion_price}` : '-'}</span></div>
                      </div>
                    </td>
                    <td className="align-top text-center">
                      <div className="space-y-1.5 text-xs">
                        <div><span className="text-slate-400">佣金率</span><span className="ml-2 font-medium text-orange-500">{m.commission_rate || '-'}</span></div>
                        <div><span className="text-slate-400">佣金</span><span className="ml-2 font-semibold text-orange-600">{m.commission_amount || '-'}</span></div>
                      </div>
                    </td>
                    <td className="align-top">
                      <div className="space-y-1.5">
                        <div className="truncate text-sm text-slate-700 dark:text-slate-200" title={m.shop_title || '-'}>{m.shop_title || '-'}</div>
                        <div className="text-xs text-slate-400">销量：{m.volume || '-'}</div>
                      </div>
                    </td>
                    <td className="align-top">
                      <div className="space-y-1.5">
                        <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${publishStatusMap[m.publish_status].className}`}>
                          {publishStatusMap[m.publish_status].text}
                        </span>
                        <div className="truncate font-mono text-xs text-slate-500 dark:text-slate-400" title={m.published_item_id || '-'}>
                          {m.published_item_id || '未生成发布商品ID'}
                        </div>
                        <div className="text-xs text-slate-400">{m.published_at || '-'}</div>
                      </div>
                    </td>
                    {/* 淘口令 */}
                    <td className="align-top">
                      <div className="space-y-2">
                        <div className="inline-flex max-w-full items-center rounded-md bg-blue-50 px-2 py-1 font-mono text-xs text-blue-600 dark:bg-blue-900/20 dark:text-blue-300">
                          <span className="truncate" title={m.publish_random_str || '-'}>{m.publish_random_str || '无随机字符'}</span>
                        </div>
                        {m.tpwd ? (
                          <button onClick={() => handleCopy(m.tpwd, '淘口令')} className="inline-flex max-w-full items-center gap-1 rounded-md border border-orange-200 bg-orange-50 px-2 py-1 text-xs font-mono text-orange-600 transition-colors hover:bg-orange-100 dark:border-orange-900/40 dark:bg-orange-900/20 dark:text-orange-300" title={m.tpwd}><Copy className="h-3.5 w-3.5 shrink-0" /><span className="truncate">{m.tpwd}</span></button>
                        ) : (
                          <span className="text-xs text-slate-400">暂无淘口令</span>
                        )}
                        {m.short_url ? (
                          <button onClick={() => handleCopy(m.short_url, '短连接')} className="inline-flex max-w-full items-center gap-1 rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-mono text-emerald-600 transition-colors hover:bg-emerald-100 dark:border-emerald-900/40 dark:bg-emerald-900/20 dark:text-emerald-300" title={m.short_url}><Copy className="h-3.5 w-3.5 shrink-0" /><span className="truncate">{m.short_url}</span></button>
                        ) : (
                          <span className="text-xs text-slate-400">暂无短连接</span>
                        )}
                      </div>
                    </td>
                    <td className="align-top text-xs text-slate-400">{m.created_at}</td>
                    {/* 操作 */}
                    <td className="sticky right-0 z-10 bg-white/95 text-center backdrop-blur dark:bg-slate-800/95">
                      <div className="flex items-center justify-center gap-1">
                        <button onClick={() => setViewMaterial(m)} className="p-1.5 rounded hover:bg-purple-50 dark:hover:bg-purple-900/30 text-purple-500" title="查看明细"><Eye className="w-3.5 h-3.5" /></button>
                        <button onClick={() => handleCopy(m.coupon_url || m.click_url, '推广链接')} className="p-1.5 rounded hover:bg-blue-50 dark:hover:bg-blue-900/30 text-blue-500" title="复制链接"><Copy className="w-3.5 h-3.5" /></button>
                        {(m.coupon_url || m.click_url) && (
                          <a href={m.coupon_url || m.click_url} target="_blank" rel="noopener noreferrer" className="p-1.5 rounded hover:bg-emerald-50 dark:hover:bg-emerald-900/30 text-emerald-500" title="打开链接"><ExternalLink className="w-3.5 h-3.5" /></a>
                        )}
                        <button onClick={() => setEditMaterial(m)} className="p-1.5 rounded hover:bg-amber-50 dark:hover:bg-amber-900/30 text-amber-500" title="编辑"><Pencil className="w-3.5 h-3.5" /></button>
                        <button onClick={() => handleDelete(m.id)} disabled={deletingId === m.id} className="p-1.5 rounded hover:bg-red-50 dark:hover:bg-red-900/30 text-red-500 disabled:opacity-50" title="删除">{deletingId === m.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}</button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <DataTablePagination
          total={total}
          page={page}
          totalPages={totalPages || 1}
          pageSize={pageSize}
          loading={loading}
          onPageChange={handlePageChange}
          onPageSizeChange={handlePageSizeChange}
        />
      </div>

      {/* 明细弹窗 */}
      {viewMaterial && <MaterialDetailModal material={viewMaterial} onClose={() => setViewMaterial(null)} />}

      {/* 编辑弹窗 */}
      {editMaterial && <MaterialEditModal material={editMaterial} onClose={() => setEditMaterial(null)} onSaved={fetchList} />}
    </div>
  )
}
