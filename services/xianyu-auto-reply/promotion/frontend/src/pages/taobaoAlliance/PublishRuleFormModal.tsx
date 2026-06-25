/**
 * 发布规则 - 新建/编辑弹窗
 *
 * 功能：
 * 1. 新建发布规则（选择闲鱼账号、设置每日发布数量）
 * 2. 编辑已有发布规则
 * 3. 加载闲鱼账号下拉列表
 */
import { useState, useEffect } from 'react'
import { X, Loader2 } from 'lucide-react'
import { createPublishRule, updatePublishRule, listXYAccounts } from '@/api/publishRule'
import type { PublishRule, XYAccountOption } from '@/api/publishRule'
import { useUIStore } from '@/store/uiStore'
import { getApiErrorMessage } from '@/utils/request'

interface Props {
  rule: PublishRule | null
  onClose: () => void
  onSaved: () => void
}

export function PublishRuleFormModal({ rule, onClose, onSaved }: Props) {
  const { addToast } = useUIStore()
  const isEdit = !!rule

  const [ruleName, setRuleName] = useState(rule?.rule_name || '')
  const [accountId, setAccountId] = useState(rule?.account_id || '')
  const [dailyCount, setDailyCount] = useState(rule?.daily_count || 5)
  const [enabled, setEnabled] = useState(rule?.enabled ?? true)
  const [remark, setRemark] = useState(rule?.remark || '')
  const [saving, setSaving] = useState(false)

  /** 闲鱼账号列表 */
  const [accounts, setAccounts] = useState<XYAccountOption[]>([])
  const [loadingAccounts, setLoadingAccounts] = useState(false)

  /** 加载闲鱼账号 */
  useEffect(() => {
    const fetchAccounts = async () => {
      setLoadingAccounts(true)
      try {
        const res = await listXYAccounts()
        if (res.success && res.data) {
          setAccounts(res.data)
          // 如果没有预选账号且有可用账号，默认选第一个
          if (!accountId && res.data.length > 0) {
            setAccountId(res.data[0].account_id)
          }
        } else {
          addToast({ type: 'error', message: res.message || '加载闲鱼账号失败' })
        }
      } catch (err) {
        addToast({ type: 'error', message: getApiErrorMessage(err) })
      } finally {
        setLoadingAccounts(false)
      }
    }
    fetchAccounts()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  /** 保存 */
  const handleSave = async () => {
    if (!ruleName.trim()) {
      addToast({ type: 'error', message: '请输入规则名称' })
      return
    }
    if (!accountId) {
      addToast({ type: 'error', message: '请选择闲鱼账号' })
      return
    }

    setSaving(true)
    try {
      const data = {
        rule_name: ruleName.trim(),
        account_id: accountId,
        daily_count: dailyCount,
        enabled,
        remark: remark.trim(),
      }

      const res = isEdit
        ? await updatePublishRule(rule!.id, data)
        : await createPublishRule(data)

      if (res.success) {
        addToast({ type: 'success', message: isEdit ? '更新成功' : '创建成功' })
        onSaved()
        onClose()
      } else {
        addToast({ type: 'error', message: res.message || '保存失败' })
      }
    } catch (err) {
      addToast({ type: 'error', message: getApiErrorMessage(err) })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        {/* 头部 */}
        <div className="flex items-center justify-between px-6 py-4 border-b dark:border-slate-700">
          <h3 className="text-lg font-semibold">{isEdit ? '编辑发布规则' : '新建发布规则'}</h3>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-slate-700">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* 表单 */}
        <div className="px-6 py-4 space-y-4">
          {/* 规则名称 */}
          <div>
            <label className="block text-sm font-medium mb-1">规则名称 <span className="text-red-500">*</span></label>
            <input
              type="text"
              value={ruleName}
              onChange={(e) => setRuleName(e.target.value)}
              placeholder="请输入规则名称"
              className="input-ios w-full"
              maxLength={120}
            />
          </div>

          {/* 闲鱼账号 */}
          <div>
            <label className="block text-sm font-medium mb-1">闲鱼账号 <span className="text-red-500">*</span></label>
            {loadingAccounts ? (
              <div className="flex items-center gap-2 text-gray-400 text-sm py-2">
                <Loader2 className="w-4 h-4 animate-spin" />加载中...
              </div>
            ) : accounts.length === 0 ? (
              <p className="text-sm text-orange-500">暂无可用的闲鱼账号，请先在主系统中添加</p>
            ) : (
              <select
                value={accountId}
                onChange={(e) => setAccountId(e.target.value)}
                className="input-ios w-full"
              >
                <option value="">请选择账号</option>
                {accounts.map((a) => (
                  <option key={a.account_id} value={a.account_id}>
                    {a.display_name}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* 每日发布数量 */}
          <div>
            <label className="block text-sm font-medium mb-1">每日发布数量</label>
            <input
              type="number"
              value={dailyCount}
              onChange={(e) => setDailyCount(Math.max(1, parseInt(e.target.value) || 1))}
              min={1}
              className="input-ios w-full"
            />
            <p className="text-xs text-gray-400 mt-1">最小值为 1，不限制上限</p>
          </div>

          {/* 是否启用 */}
          <div className="flex items-center gap-3">
            <label className="text-sm font-medium">是否启用</label>
            <button
              onClick={() => setEnabled(!enabled)}
              className={`relative inline-flex h-5 w-10 items-center rounded-full transition-colors ${
                enabled ? 'bg-blue-500' : 'bg-gray-300 dark:bg-slate-600'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                  enabled ? 'translate-x-5' : 'translate-x-0.5'
                }`}
              />
            </button>
          </div>

          {/* 备注 */}
          <div>
            <label className="block text-sm font-medium mb-1">备注</label>
            <textarea
              value={remark}
              onChange={(e) => setRemark(e.target.value)}
              placeholder="可选备注"
              className="input-ios w-full h-20 resize-none"
              maxLength={255}
            />
          </div>
        </div>

        {/* 底部按钮 */}
        <div className="flex justify-end gap-3 px-6 py-4 border-t dark:border-slate-700">
          <button onClick={onClose} className="btn-ios-secondary">取消</button>
          <button onClick={handleSave} disabled={saving} className="btn-ios-primary flex items-center gap-1.5">
            {saving && <Loader2 className="w-4 h-4 animate-spin" />}
            {isEdit ? '保存' : '创建'}
          </button>
        </div>
      </div>
    </div>
  )
}
