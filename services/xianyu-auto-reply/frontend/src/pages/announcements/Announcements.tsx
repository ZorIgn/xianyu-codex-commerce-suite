/**
 * 公告管理页面
 * 
 * 功能：
 * 1. 查看公告列表（按创建时间倒序）
 * 2. 管理员可新增、修改、删除公告
 */
import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
  Megaphone,
  RefreshCw,
  Plus,
  Edit2,
  Trash2,
  X,
  Loader2,
} from 'lucide-react'
import { getAnnouncements, createAnnouncement, updateAnnouncement, deleteAnnouncement } from '@/api/announcements'
import type { Announcement } from '@/api/announcements'
import { useUIStore } from '@/store/uiStore'
import { useAuthStore } from '@/store/authStore'
import { PageLoading } from '@/components/common/Loading'
import { ConfirmModal } from '@/components/common/ConfirmModal'

export function Announcements() {
  const { addToast } = useUIStore()
  const { isAuthenticated, token, _hasHydrated, user } = useAuthStore()
  const [loading, setLoading] = useState(true)
  const [announcements, setAnnouncements] = useState<Announcement[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  // 新建/编辑弹窗
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [formTitle, setFormTitle] = useState('')
  const [formContent, setFormContent] = useState('')
  const [saving, setSaving] = useState(false)

  // 删除确认弹窗
  const [deleteConfirm, setDeleteConfirm] = useState<{ open: boolean; announcement: Announcement | null }>({
    open: false,
    announcement: null,
  })
  const [deleting, setDeleting] = useState(false)

  const loadAnnouncements = async () => {
    if (!_hasHydrated || !isAuthenticated || !token) return
    try {
      setLoading(true)
      const result = await getAnnouncements({ page, page_size: pageSize })
      if (result.success && result.data) {
        setAnnouncements(result.data.items)
        setTotal(result.data.total)
      }
    } catch {
      addToast({ type: 'error', message: '加载公告列表失败' })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAnnouncements()
  }, [_hasHydrated, isAuthenticated, token, page, pageSize])

  const openAddModal = () => {
    setEditingId(null)
    setFormTitle('')
    setFormContent('')
    setIsModalOpen(true)
  }

  const openEditModal = (ann: Announcement) => {
    setEditingId(ann.id)
    setFormTitle(ann.title)
    setFormContent(ann.content)
    setIsModalOpen(true)
  }

  const handleSubmit = async () => {
    if (!formTitle.trim()) {
      addToast({ type: 'warning', message: '请输入公告标题' })
      return
    }
    if (!formContent.trim()) {
      addToast({ type: 'warning', message: '请输入公告内容' })
      return
    }
    setSaving(true)
    try {
      if (editingId) {
        const result = await updateAnnouncement(editingId, {
          title: formTitle.trim(),
          content: formContent.trim(),
        })
        if (result.success) {
          addToast({ type: 'success', message: '公告更新成功' })
          setIsModalOpen(false)
          loadAnnouncements()
        } else {
          addToast({ type: 'error', message: result.message || '更新失败' })
        }
      } else {
        const result = await createAnnouncement({
          title: formTitle.trim(),
          content: formContent.trim(),
        })
        if (result.success) {
          addToast({ type: 'success', message: '公告发布成功' })
          setIsModalOpen(false)
          loadAnnouncements()
        } else {
          addToast({ type: 'error', message: result.message || '发布失败' })
        }
      }
    } catch {
      addToast({ type: 'error', message: editingId ? '更新失败' : '发布失败' })
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (ann: Announcement) => {
    setDeleting(true)
    try {
      const result = await deleteAnnouncement(ann.id)
      if (result.success) {
        addToast({ type: 'success', message: '删除成功' })
        setDeleteConfirm({ open: false, announcement: null })
        loadAnnouncements()
      } else {
        addToast({ type: 'error', message: result.message || '删除失败' })
      }
    } catch {
      addToast({ type: 'error', message: '删除失败' })
    } finally {
      setDeleting(false)
    }
  }

  if (loading && announcements.length === 0) {
    return <PageLoading />
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="page-title">公告管理</h1>
          <p className="page-description">查看系统公告信息</p>
        </div>
        <div className="flex gap-3">
          {user?.is_admin && (
            <button onClick={openAddModal} className="btn-ios-primary">
              <Plus className="w-4 h-4" />
              发布公告
            </button>
          )}
          <button onClick={loadAnnouncements} className="btn-ios-secondary">
            <RefreshCw className="w-4 h-4" />
            刷新
          </button>
        </div>
      </div>

      {/* 列表 */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="vben-card">
        <div className="vben-card-header">
          <h2 className="vben-card-title">
            <Megaphone className="w-4 h-4" />
            公告列表
          </h2>
          <span className="badge-primary">{total} 条</span>
        </div>
        <div className="divide-y divide-slate-100 dark:divide-slate-700">
          {announcements.length === 0 ? (
            <div className="py-12 text-center text-slate-500">
              <Megaphone className="w-12 h-12 mx-auto mb-3 text-slate-300" />
              <p>暂无公告</p>
            </div>
          ) : (
            announcements.map((ann) => (
              <div
                key={ann.id}
                className="p-4 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <Megaphone className="w-4 h-4 text-blue-500" />
                      <span className="font-medium text-slate-900 dark:text-slate-100">
                        {ann.title}
                      </span>
                    </div>
                    <p className="text-sm text-slate-600 dark:text-slate-400 whitespace-pre-wrap">
                      {ann.content}
                    </p>
                    <div className="flex items-center gap-3 mt-2 text-xs text-slate-400">
                      <span>发布时间：{new Date(ann.created_at).toLocaleString('zh-CN')}</span>
                      {ann.updated_at !== ann.created_at && (
                        <span>更新时间：{new Date(ann.updated_at).toLocaleString('zh-CN')}</span>
                      )}
                    </div>
                  </div>
                  {user?.is_admin && (
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => openEditModal(ann)}
                        className="p-2 text-slate-400 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-lg transition-colors"
                        title="编辑"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => setDeleteConfirm({ open: true, announcement: ann })}
                        className="p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                        title="删除"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
        {/* 分页 */}
        {total > 0 && (
          <div className="p-4 border-t border-slate-100 dark:border-slate-700 flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <span>每页</span>
              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value))
                  setPage(1)
                }}
                className="input-ios py-1 px-2 w-20"
              >
                <option value={10}>10条</option>
                <option value={20}>20条</option>
                <option value={50}>50条</option>
                <option value={100}>100条</option>
              </select>
              <span>共 {total} 条</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="btn-ios-secondary btn-sm"
              >
                上一页
              </button>
              <span className="px-3 py-1.5 text-sm text-slate-500">
                {page} / {Math.ceil(total / pageSize)}
              </span>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={page >= Math.ceil(total / pageSize)}
                className="btn-ios-secondary btn-sm"
              >
                下一页
              </button>
            </div>
          </div>
        )}
      </motion.div>

      {/* 新建/编辑弹窗 */}
      {isModalOpen && (
        <div className="modal-overlay">
          <div className="modal-content max-w-lg">
            <div className="modal-header">
              <h2 className="text-lg font-semibold">{editingId ? '编辑公告' : '发布公告'}</h2>
              <button onClick={() => setIsModalOpen(false)} className="p-1 hover:bg-gray-100 dark:hover:bg-slate-700 rounded-lg">
                <X className="w-4 h-4 text-gray-500" />
              </button>
            </div>
            <div className="modal-body space-y-4">
              <div className="input-group">
                <label className="input-label">公告标题 *</label>
                <input
                  type="text"
                  value={formTitle}
                  onChange={(e) => setFormTitle(e.target.value)}
                  placeholder="请输入公告标题"
                  className="input-ios"
                  maxLength={200}
                />
              </div>
              <div className="input-group">
                <label className="input-label">公告内容 *</label>
                <textarea
                  value={formContent}
                  onChange={(e) => setFormContent(e.target.value)}
                  placeholder="请输入公告内容"
                  className="input-ios min-h-[150px] resize-none"
                  maxLength={5000}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button onClick={() => setIsModalOpen(false)} className="btn-ios-secondary" disabled={saving}>
                取消
              </button>
              <button onClick={handleSubmit} className="btn-ios-primary" disabled={saving}>
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                {editingId ? '保存' : '发布'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 删除确认弹窗 */}
      <ConfirmModal
        isOpen={deleteConfirm.open}
        title="删除确认"
        message="确定要删除这条公告吗？删除后无法恢复。"
        confirmText="删除"
        cancelText="取消"
        type="danger"
        loading={deleting}
        onConfirm={() => deleteConfirm.announcement && handleDelete(deleteConfirm.announcement)}
        onCancel={() => setDeleteConfirm({ open: false, announcement: null })}
      />
    </div>
  )
}
