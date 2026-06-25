/**
 * 对接弹窗组件
 * 
 * 功能：
 * 1. 显示对接名称、对接价格（只读）
 * 2. 提交对接记录
 */
import { useState, useEffect } from 'react'
import { X, RefreshCw } from 'lucide-react'
import { createDockRecord } from '@/api/distribution'
import type { SupplyCard } from '@/api/distribution'
import { useUIStore } from '@/store/uiStore'
import { getSystemSettings } from '@/api/settings'

interface DockModalProps {
  /** 是否显示弹窗 */
  isOpen: boolean
  /** 关闭弹窗回调 */
  onClose: () => void
  /** 对接成功回调 */
  onSuccess: () => void
  /** 当前选中的货源卡券 */
  card: SupplyCard | null
}

export function DockModal({ isOpen, onClose, onSuccess, card }: DockModalProps) {
  const { addToast } = useUIStore()
  const [submitting, setSubmitting] = useState(false)
  const [dockName, setDockName] = useState('')
  const [remark, setRemark] = useState('')
  const [feeRate, setFeeRate] = useState('')
  const [feeType, setFeeType] = useState('fixed')

  // 弹窗打开时初始化表单并获取手续费设置
  useEffect(() => {
    if (isOpen && card) {
      setDockName(card.name || '')
      setRemark('')
      getSystemSettings().then(res => {
        if (res.success && res.data) {
          setFeeRate(res.data['distribution.fee_rate'] as string || '0')
          setFeeType(res.data['distribution.fee_type'] as string || 'fixed')
        }
      })
    }
  }, [isOpen, card])

  // 表单校验
  const validate = (): boolean => {
    if (!dockName.trim()) {
      addToast({ type: 'warning', message: '请输入对接名称' })
      return false
    }
    return true
  }

  // 提交对接
  const handleSubmit = async () => {
    if (!card || !validate()) return

    setSubmitting(true)
    try {
      const result = await createDockRecord({
        card_id: card.id,
        dock_name: dockName.trim(),
        remark: remark.trim() || undefined,
      })
      if (result.success) {
        addToast({ type: 'success', message: '对接成功' })
        onSuccess()
        onClose()
      } else {
        addToast({ type: 'error', message: result.message || '对接失败' })
      }
    } catch {
      addToast({ type: 'error', message: '对接失败' })
    } finally {
      setSubmitting(false)
    }
  }

  if (!isOpen || !card) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* 遮罩 */}
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />

      {/* 弹窗内容 */}
      <div className="relative w-full max-w-lg mx-4 bg-white dark:bg-slate-800 rounded-xl shadow-2xl">
        {/* 头部 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-700">
          <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
            对接货源
          </h3>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
          >
            <X className="w-5 h-5 text-slate-500" />
          </button>
        </div>

        {/* 表单 */}
        <div className="px-6 py-5 space-y-4">
          {/* 对接名称 */}
          <div>
            <label className="input-label">
              对接名称 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={dockName}
              onChange={(e) => setDockName(e.target.value)}
              className="input-ios"
              placeholder="请输入对接名称"
            />
          </div>

          {/* 对接价格（只读） */}
          <div>
            <label className="input-label">对接价格（元）</label>
            <input
              type="text"
              value={card.price ? `¥${card.price}` : '未设置'}
              disabled
              className="input-ios bg-gray-50 dark:bg-gray-800 cursor-not-allowed"
            />
          </div>

          {/* 最低售价（只读） */}
          {card.min_price && (
            <div>
              <label className="input-label">最低售价（元）</label>
              <input
                type="text"
                value={`¥${card.min_price}`}
                disabled
                className="input-ios bg-gray-50 dark:bg-gray-800 cursor-not-allowed"
              />
              <p className="text-xs text-orange-600 dark:text-orange-400 mt-1">您的售价不能低于此最低售价</p>
            </div>
          )}

          {/* 手续费提示 */}
          {card.fee_payer && (
            <div className="px-4 py-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
              <p className="text-sm text-amber-700 dark:text-amber-400">
                {card.fee_payer === 'distributor'
                  ? (feeType === 'percent'
                    ? `每笔订单您的上游需要支付订单金额的 ${feeRate}% 作为手续费`
                    : `每笔订单您的上游需要支付 ${feeRate} 元手续费`)
                  : (feeType === 'percent'
                    ? `每笔订单您需要支付订单金额的 ${feeRate}% 作为手续费`
                    : `每笔订单您需要支付 ${feeRate} 元手续费`)
                }
              </p>
            </div>
          )}

          {/* 备注 */}
          <div>
            <label className="input-label">备注</label>
            <textarea
              value={remark}
              onChange={(e) => setRemark(e.target.value)}
              className="input-ios"
              rows={3}
              placeholder="可选，填写备注信息"
            />
          </div>
        </div>

        {/* 底部按钮 */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-200 dark:border-slate-700">
          <button onClick={onClose} className="btn-ios-secondary">
            取消
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="btn-ios-primary"
          >
            {submitting ? (
              <span className="flex items-center gap-2">
                <RefreshCw className="w-4 h-4 animate-spin" />
                提交中...
              </span>
            ) : (
              '确认对接'
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
