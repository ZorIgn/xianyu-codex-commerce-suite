/**
 * 推广返佣系统 - 账号管理页面
 *
 * 功能：
 * 1. 账号列表（后端分页，固定高度表格+滚动条）
 * 2. 搜索筛选 + 账号类型筛选
 * 3. 新增账号（淘宝填 AppKey/AppSecret/推广位ID，其他填 Cookies）
 * 4. 启用/禁用
 * 5. 修改账号（统一编辑弹窗，与新增保持一致）
 */
import { useEffect, useState, useCallback } from 'react'
import { Plus, Search, RefreshCw, Edit2, X } from 'lucide-react'
import { getAccountList, addAccount, toggleAccountStatus, updateAccount } from '@/api/cookies'
import { useUIStore } from '@/store/uiStore'
import { getApiErrorMessage } from '@/utils/request'
import { PageLoading } from '@/components/common/Loading'
import { DataTablePagination } from '@/components/common/DataTablePagination'
import type { Account, AccountType } from '@/types'
import { ACCOUNT_TYPE_OPTIONS } from '@/types'

export function Accounts() {
  const { addToast } = useUIStore()

  /* -------- 列表状态 -------- */
  const [accounts, setAccounts] = useState<Account[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [keyword, setKeyword] = useState('')
  const [filterType, setFilterType] = useState('')
  const [loading, setLoading] = useState(true)

  /* -------- 弹窗状态 -------- */
  const [showAddModal, setShowAddModal] = useState(false)
  const [addCookies, setAddCookies] = useState('')
  const [addAppKey, setAddAppKey] = useState('')
  const [addAppSecret, setAddAppSecret] = useState('')
  const [addAdzoneId, setAddAdzoneId] = useState('')
  const [addRemark, setAddRemark] = useState('')
  const [addType, setAddType] = useState<AccountType>('TAOBAO')
  const [addLoading, setAddLoading] = useState(false)

  /* -------- 编辑弹窗状态 -------- */
  const [showEditModal, setShowEditModal] = useState(false)
  const [editAccount, setEditAccount] = useState<Account | null>(null)
  const [editAppKey, setEditAppKey] = useState('')
  const [editAppSecret, setEditAppSecret] = useState('')
  const [editAdzoneId, setEditAdzoneId] = useState('')
  const [editCookies, setEditCookies] = useState('')
  const [editRemark, setEditRemark] = useState('')
  const [editLoading, setEditLoading] = useState(false)

  /* -------- 加载数据 -------- */
  const loadAccounts = useCallback(async () => {
    setLoading(true)
    try {
      const res = await getAccountList({ page, page_size: pageSize, keyword, account_type: filterType })
      if (res.success && res.data) {
        setAccounts(res.data.items)
        setTotal(res.data.total)
      } else {
        addToast({ message: res.message || '获取账号列表失败', type: 'error' })
      }
    } catch (err) {
      addToast({ message: getApiErrorMessage(err), type: 'error' })
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, keyword, filterType, addToast])

  useEffect(() => {
    loadAccounts()
  }, [loadAccounts])

  /* -------- 搜索 -------- */
  const handleSearch = () => {
    setPage(1)
    loadAccounts()
  }

  /* -------- 新增账号 -------- */
  const handleAdd = async () => {
    if (addType === 'TAOBAO') {
      if (!addAppKey.trim() || !addAppSecret.trim()) {
        addToast({ message: '请填写AppKey和AppSecret', type: 'warning' })
        return
      }
      if (!addAdzoneId.trim()) {
        addToast({ message: '请填写推广位ID', type: 'warning' })
        return
      }
    } else {
      if (!addCookies.trim()) {
        addToast({ message: '请输入Cookies', type: 'warning' })
        return
      }
    }
    setAddLoading(true)
    try {
      const res = await addAccount({
        account_type: addType,
        ...(addType === 'TAOBAO'
          ? { app_key: addAppKey.trim(), app_secret: addAppSecret.trim(), adzone_id: addAdzoneId.trim() }
          : { cookies: addCookies.trim() }
        ),
        remark: addRemark.trim(),
      })
      if (res.success) {
        addToast({ message: res.message || '添加成功', type: 'success' })
        setShowAddModal(false)
        setAddCookies('')
        setAddAppKey('')
        setAddAppSecret('')
        setAddAdzoneId('')
        setAddRemark('')
        setAddType('TAOBAO')
        loadAccounts()
      } else {
        addToast({ message: res.message || '添加失败', type: 'error' })
      }
    } catch (err) {
      addToast({ message: getApiErrorMessage(err), type: 'error' })
    } finally {
      setAddLoading(false)
    }
  }

  /* -------- 打开编辑弹窗 -------- */
  const openEditModal = (account: Account) => {
    setEditAccount(account)
    setEditAppKey(account.app_key || '')
    setEditAppSecret('')
    setEditAdzoneId(account.adzone_id || '')
    setEditCookies('')
    setEditRemark(account.remark || '')
    setShowEditModal(true)
  }

  /* -------- 提交修改 -------- */
  const handleEdit = async () => {
    if (!editAccount) return
    setEditLoading(true)
    try {
      const data: Record<string, unknown> = { id: editAccount.id, remark: editRemark.trim() }
      if (editAccount.account_type === 'TAOBAO') {
        if (editAppKey.trim()) data.app_key = editAppKey.trim()
        if (editAppSecret.trim()) data.app_secret = editAppSecret.trim()
        if (editAdzoneId.trim()) data.adzone_id = editAdzoneId.trim()
      } else {
        if (editCookies.trim()) data.cookies = editCookies.trim()
      }
      const res = await updateAccount(data as Parameters<typeof updateAccount>[0])
      if (res.success) {
        addToast({ message: res.message || '修改成功', type: 'success' })
        setShowEditModal(false)
        loadAccounts()
      } else {
        addToast({ message: res.message || '修改失败', type: 'error' })
      }
    } catch (err) {
      addToast({ message: getApiErrorMessage(err), type: 'error' })
    } finally {
      setEditLoading(false)
    }
  }

  /* -------- 切换状态 -------- */
  const handleToggleStatus = async (account: Account) => {
    try {
      const res = await toggleAccountStatus({ id: account.id, enabled: !account.enabled })
      if (res.success) {
        addToast({ message: res.message || '操作成功', type: 'success' })
        loadAccounts()
      } else {
        addToast({ message: res.message || '操作失败', type: 'error' })
      }
    } catch (err) {
      addToast({ message: getApiErrorMessage(err), type: 'error' })
    }
  }

  if (loading && accounts.length === 0) return <PageLoading />

  return (
    <div>
      {/* 页面头部 */}
      <div className="page-header flex-between flex-wrap gap-3">
        <div>
          <h1 className="page-title">账号管理</h1>
          <p className="page-description">管理您的推广账号，支持淘宝、京东、美团</p>
        </div>
        <button className="btn-ios-primary" onClick={() => setShowAddModal(true)}>
          <Plus className="w-4 h-4" />
          新增账号
        </button>
      </div>

      {/* 工具栏 */}
      <div className="toolbar">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            className="input-ios pl-9"
            placeholder="搜索账号ID/备注"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          />
        </div>
        <select
          className="input-ios w-auto text-sm"
          value={filterType}
          onChange={(e) => { setFilterType(e.target.value); setPage(1) }}
        >
          <option value="">全部类型</option>
          {ACCOUNT_TYPE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        <button className="btn-ios-secondary btn-sm" onClick={handleSearch}>
          搜索
        </button>
        <button className="btn-ios-ghost btn-sm" onClick={loadAccounts}>
          <RefreshCw className="w-4 h-4" />
          刷新
        </button>
      </div>

      {/* 表格 */}
      <div className="vben-card">
        <div className="table-ios-container" style={{ maxHeight: 'calc(100vh - 340px)' }}>
          <table className="table-ios">
            <thead className="sticky top-0 z-10">
              <tr>
                <th>账号ID</th>
                <th>账号类型</th>
                <th>状态</th>
                <th>备注</th>
                <th>创建时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {accounts.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-12 text-slate-400">
                    暂无账号数据
                  </td>
                </tr>
              ) : (
                accounts.map((account) => (
                  <tr key={account.id}>
                    <td className="font-mono text-xs">{account.account_id}</td>
                    <td>
                      <span className="badge-info">{account.account_type_label}</span>
                    </td>
                    <td>
                      <button
                        onClick={() => handleToggleStatus(account)}
                        className={account.enabled ? 'badge-success cursor-pointer' : 'badge-danger cursor-pointer'}
                      >
                        {account.enabled ? '启用' : '禁用'}
                      </button>
                    </td>
                    <td className="max-w-[200px] truncate">{account.remark || '-'}</td>
                    <td className="text-xs text-slate-500">{account.created_at || '-'}</td>
                    <td>
                      <button
                        className="btn-ios-ghost btn-sm"
                        onClick={() => openEditModal(account)}
                        title="修改"
                      >
                        <Edit2 className="w-3.5 h-3.5 mr-1" />
                        修改
                      </button>
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
          totalPages={Math.ceil(total / pageSize) || 1}
          pageSize={pageSize}
          loading={loading}
          onPageChange={setPage}
          onPageSizeChange={(size) => {
            setPageSize(size)
            setPage(1)
          }}
        />
      </div>

      {/* ========== 新增账号弹窗 ========== */}
      {showAddModal && (
        <div className="modal-overlay">
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">新增账号</h3>
              <button className="modal-close" onClick={() => setShowAddModal(false)}>
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="modal-body space-y-4">
              <div className="input-group">
                <label className="input-label">账号类型</label>
                <select
                  className="input-ios"
                  value={addType}
                  onChange={(e) => setAddType(e.target.value as AccountType)}
                >
                  {ACCOUNT_TYPE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
              {addType === 'TAOBAO' ? (
                <>
                  <div className="input-group">
                    <label className="input-label">AppKey</label>
                    <input
                      type="text"
                      className="input-ios"
                      placeholder="请输入淘宝开放平台AppKey"
                      value={addAppKey}
                      onChange={(e) => setAddAppKey(e.target.value)}
                    />
                  </div>
                  <div className="input-group">
                    <label className="input-label">AppSecret</label>
                    <input
                      type="text"
                      className="input-ios"
                      placeholder="请输入淘宝开放平台AppSecret"
                      value={addAppSecret}
                      onChange={(e) => setAddAppSecret(e.target.value)}
                    />
                  </div>
                  <div className="input-group">
                    <label className="input-label">推广位ID</label>
                    <input
                      type="text"
                      className="input-ios"
                      placeholder="纯数字或mm_xxx_xxx_xxx格式"
                      value={addAdzoneId}
                      onChange={(e) => setAddAdzoneId(e.target.value)}
                    />
                    <p className="text-xs text-gray-400 mt-1">支持纯数字或完整PID格式，系统会自动解析</p>
                  </div>
                </>
              ) : (
                <div className="input-group">
                  <label className="input-label">Cookies</label>
                  <textarea
                    className="input-ios min-h-[120px] resize-y"
                    placeholder="请粘贴账号Cookies"
                    value={addCookies}
                    onChange={(e) => setAddCookies(e.target.value)}
                  />
                </div>
              )}
              <div className="input-group">
                <label className="input-label">备注（可选）</label>
                <input
                  type="text"
                  className="input-ios"
                  placeholder="为账号添加备注"
                  value={addRemark}
                  onChange={(e) => setAddRemark(e.target.value)}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn-ios-secondary" onClick={() => setShowAddModal(false)}>取消</button>
              <button className="btn-ios-primary" onClick={handleAdd} disabled={addLoading}>
                {addLoading ? '添加中...' : '确认添加'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========== 统一编辑弹窗 ========== */}
      {showEditModal && editAccount && (
        <div className="modal-overlay">
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">修改账号</h3>
              <button className="modal-close" onClick={() => setShowEditModal(false)}>
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="modal-body space-y-4">
              <div className="input-group">
                <label className="input-label">账号类型</label>
                <input type="text" className="input-ios bg-gray-50 dark:bg-slate-800" value={editAccount.account_type_label} disabled />
              </div>
              {editAccount.account_type === 'TAOBAO' ? (
                <>
                  <div className="input-group">
                    <label className="input-label">AppKey</label>
                    <input
                      type="text"
                      className="input-ios"
                      placeholder="请输入淘宝开放平台AppKey"
                      value={editAppKey}
                      onChange={(e) => setEditAppKey(e.target.value)}
                    />
                  </div>
                  <div className="input-group">
                    <label className="input-label">AppSecret</label>
                    <input
                      type="text"
                      className="input-ios"
                      placeholder={editAccount.app_secret_masked ? `当前: ${editAccount.app_secret_masked}，留空不修改` : '请输入淘宝开放平台AppSecret'}
                      value={editAppSecret}
                      onChange={(e) => setEditAppSecret(e.target.value)}
                    />
                  </div>
                  <div className="input-group">
                    <label className="input-label">推广位ID</label>
                    <input
                      type="text"
                      className="input-ios"
                      placeholder="纯数字或mm_xxx_xxx_xxx格式"
                      value={editAdzoneId}
                      onChange={(e) => setEditAdzoneId(e.target.value)}
                    />
                    <p className="text-xs text-gray-400 mt-1">支持纯数字或完整PID格式，系统会自动解析</p>
                  </div>
                </>
              ) : (
                <div className="input-group">
                  <label className="input-label">Cookies</label>
                  <textarea
                    className="input-ios min-h-[120px] resize-y"
                    placeholder="留空不修改，填写则替换"
                    value={editCookies}
                    onChange={(e) => setEditCookies(e.target.value)}
                  />
                </div>
              )}
              <div className="input-group">
                <label className="input-label">备注</label>
                <input
                  type="text"
                  className="input-ios"
                  placeholder="为账号添加备注"
                  value={editRemark}
                  onChange={(e) => setEditRemark(e.target.value)}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn-ios-secondary" onClick={() => setShowEditModal(false)}>取消</button>
              <button className="btn-ios-primary" onClick={handleEdit} disabled={editLoading}>
                {editLoading ? '保存中...' : '保存'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
