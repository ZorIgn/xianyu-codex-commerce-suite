/**
 * 充值弹窗组件
 * 
 * 功能：
 * 1. 输入充值金额
 * 2. 调用后端生成支付宝当面付二维码
 * 3. 展示二维码供用户扫码支付
 * 4. 轮询支付状态，支付成功后自动关闭
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { X, Loader2, CheckCircle, AlertCircle } from 'lucide-react'
import { QRCodeSVG } from 'qrcode.react'
import { createRecharge, getRechargeStatus } from '@/api/payment'
import { useUIStore } from '@/store/uiStore'

interface RechargeModalProps {
  visible: boolean
  onClose: () => void
  onSuccess: () => void
}

/** 充值步骤 */
type Step = 'input' | 'qrcode' | 'success' | 'error'

export function RechargeModal({ visible, onClose, onSuccess }: RechargeModalProps) {
  const { addToast } = useUIStore()
  const [step, setStep] = useState<Step>('input')
  const [amount, setAmount] = useState('')
  const [loading, setLoading] = useState(false)
  const [qrCode, setQrCode] = useState('')
  const [orderNo, setOrderNo] = useState('')
  const [errorMsg, setErrorMsg] = useState('')
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  /** 清理轮询定时器 */
  const clearPoll = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  /** 重置状态 */
  const reset = useCallback(() => {
    setStep('input')
    setAmount('')
    setLoading(false)
    setQrCode('')
    setOrderNo('')
    setErrorMsg('')
    clearPoll()
  }, [clearPoll])

  /** 关闭弹窗 */
  const handleClose = useCallback(() => {
    clearPoll()
    reset()
    onClose()
  }, [clearPoll, reset, onClose])

  /** 组件卸载时清理 */
  useEffect(() => {
    return () => clearPoll()
  }, [clearPoll])

  /** 提交充值 */
  const handleSubmit = async () => {
    if (!amount || loading) return

    const num = parseFloat(amount)
    if (isNaN(num) || num <= 0) {
      addToast({ message: '请输入有效的充值金额', type: 'error' })
      return
    }
    if (num > 10000) {
      addToast({ message: '单次充值金额不能超过10000元', type: 'error' })
      return
    }

    setLoading(true)
    try {
      const result = await createRecharge(amount)
      if (result.success && result.data) {
        setQrCode(result.data.qr_code)
        setOrderNo(result.data.order_no)
        setStep('qrcode')
        startPolling(result.data.order_no)
      } else {
        setErrorMsg(result.message || '创建充值订单失败')
        setStep('error')
      }
    } catch {
      setErrorMsg('网络错误，请稍后重试')
      setStep('error')
    } finally {
      setLoading(false)
    }
  }

  /** 开始轮询支付状态 */
  const startPolling = (no: string) => {
    clearPoll()
    pollRef.current = setInterval(async () => {
      try {
        const res = await getRechargeStatus(no)
        if (res.success && res.data?.status === 'paid') {
          clearPoll()
          setStep('success')
          addToast({ message: '充值成功', type: 'success' })
          // 延迟关闭，让用户看到成功状态
          setTimeout(() => {
            onSuccess()
            handleClose()
          }, 1500)
        }
      } catch {
        // 轮询失败不做处理，继续重试
      }
    }, 3000)
  }

  if (!visible) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-slate-800 rounded-xl p-6 w-full max-w-md mx-4 shadow-xl">
        {/* 标题栏 */}
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            余额充值
          </h3>
          <button
            onClick={handleClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* 输入金额步骤 */}
        {step === 'input' && (
          <div className="space-y-4">
            <div className="input-group">
              <label className="input-label">充值金额（元）</label>
              <input
                type="text"
                value={amount}
                onChange={(e) => {
                  const val = e.target.value
                  if (val === '' || /^\d*\.?\d{0,2}$/.test(val)) {
                    setAmount(val)
                  }
                }}
                placeholder="请输入充值金额"
                className="input-ios text-lg"
                autoFocus
              />
            </div>
            {/* 快捷金额 */}
            <div className="flex flex-wrap gap-2">
              {['10', '20', '50', '100', '200', '500'].map((v) => (
                <button
                  key={v}
                  onClick={() => setAmount(v)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    amount === v
                      ? 'bg-blue-500 text-white'
                      : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600'
                  }`}
                >
                  ¥{v}
                </button>
              ))}
            </div>
            <button
              onClick={handleSubmit}
              disabled={!amount || loading}
              className="btn-ios-primary w-full"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  生成支付二维码中...
                </>
              ) : (
                '确认充值'
              )}
            </button>
          </div>
        )}

        {/* 二维码步骤 */}
        {step === 'qrcode' && (
          <div className="space-y-4 text-center">
            <p className="text-sm text-slate-500 dark:text-slate-400">
              请使用支付宝扫描下方二维码完成支付
            </p>
            <div className="flex justify-center">
              <div className="p-4 bg-white rounded-xl inline-block">
                <QRCodeSVG value={qrCode} size={200} />
              </div>
            </div>
            <div className="text-2xl font-bold text-amber-600 dark:text-amber-400">
              ¥{amount}
            </div>
            <p className="text-xs text-slate-400">
              订单号: {orderNo}
            </p>
            <div className="flex items-center justify-center gap-2 text-sm text-blue-500">
              <Loader2 className="w-4 h-4 animate-spin" />
              等待支付中...
            </div>
          </div>
        )}

        {/* 成功步骤 */}
        {step === 'success' && (
          <div className="space-y-4 text-center py-4">
            <CheckCircle className="w-16 h-16 text-green-500 mx-auto" />
            <p className="text-lg font-semibold text-green-600 dark:text-green-400">
              充值成功
            </p>
            <p className="text-sm text-slate-500">
              ¥{amount} 已充入账户余额
            </p>
          </div>
        )}

        {/* 错误步骤 */}
        {step === 'error' && (
          <div className="space-y-4 text-center py-4">
            <AlertCircle className="w-16 h-16 text-red-500 mx-auto" />
            <p className="text-lg font-semibold text-red-600 dark:text-red-400">
              充值失败
            </p>
            <p className="text-sm text-slate-500">{errorMsg}</p>
            <button onClick={reset} className="btn-ios-secondary">
              重新充值
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
