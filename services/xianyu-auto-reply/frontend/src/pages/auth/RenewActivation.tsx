/**
 * 激活码续期页面（公开页面，无需登录）
 *
 * 功能：
 * 1. 输入机器码（32位十六进制）
 * 2. 点击按钮生成续期码（默认5天）
 * 3. 显示续期码，支持一键复制
 */
import { useState } from 'react'
import { motion } from 'framer-motion'
import { RefreshCw, Copy, Check } from 'lucide-react'
import { generateRenewCode, type RenewResult } from '@/api/activation'
import { useUIStore } from '@/store/uiStore'
import { AuthNavbar, PublicPageFooter } from '@/components/common/AuthNavbar'
import { ButtonLoading } from '@/components/common/Loading'

export function RenewActivation() {
  const { addToast } = useUIStore()
  const [machineId, setMachineId] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<RenewResult | null>(null)
  const [copied, setCopied] = useState(false)

  /** 校验机器码格式 */
  const validateMachineId = (id: string): string | null => {
    const trimmed = id.trim().toUpperCase()
    if (!trimmed) return '请输入机器码'
    if (trimmed.length !== 32) return `机器码长度应为32位，当前${trimmed.length}位`
    if (!/^[0-9A-F]{32}$/.test(trimmed)) return '机器码应为十六进制字符串（0-9, A-F）'
    return null
  }

  /** 提交生成续期码 */
  const handleGenerate = async () => {
    const error = validateMachineId(machineId)
    if (error) {
      addToast({ type: 'error', message: error })
      return
    }

    setLoading(true)
    setResult(null)
    try {
      const resp = await generateRenewCode(machineId.trim().toUpperCase())
      if (resp.success && resp.data) {
        setResult(resp.data)
        addToast({ type: 'success', message: '续期码生成成功' })
      } else {
        addToast({ type: 'error', message: resp.message || '生成失败' })
      }
    } catch {
      addToast({ type: 'error', message: '请求失败，请检查网络连接' })
    } finally {
      setLoading(false)
    }
  }

  /** 复制续期码到剪贴板 */
  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      addToast({ type: 'success', message: '已复制到剪贴板' })
      setTimeout(() => setCopied(false), 2000)
    } catch {
      addToast({ type: 'error', message: '复制失败，请手动复制' })
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 transition-colors duration-200">
      <AuthNavbar />


      {/* 主内容区 */}
      <div className="pt-20 pb-10 px-4 sm:px-6 flex items-start justify-center min-h-screen">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="w-full max-w-lg"
        >
          {/* 页面标题 */}
          <div className="text-center mb-6">
            <div className="w-14 h-14 rounded-xl bg-green-500 text-white mx-auto mb-4 flex items-center justify-center">
              <RefreshCw className="w-7 h-7" />
            </div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">激活码续期</h1>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">
              输入机器码，获取 <span className="text-green-600 dark:text-green-400 font-medium">5天</span> 续期码
            </p>
          </div>

          {/* 表单卡片 */}
          <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 p-5 sm:p-8">
            <div className="space-y-4">
              {/* 机器码输入 */}
              <div className="input-group">
                <label className="input-label">机器码</label>
                <div className="relative">
                  <RefreshCw className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input
                    type="text"
                    value={machineId}
                    onChange={(e) => setMachineId(e.target.value.toUpperCase())}
                    placeholder="请输入32位机器码"
                    maxLength={32}
                    className="input-ios pl-9 font-mono text-sm"
                  />
                </div>
                <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
                  机器码为32位十六进制字符串，可在启动器中查看
                </p>
              </div>

              {/* 生成按钮 */}
              <button
                onClick={handleGenerate}
                disabled={loading}
                className="w-full btn-ios-primary"
              >
                {loading ? <ButtonLoading /> : '生成续期码'}
              </button>
            </div>

            {/* 结果展示 */}
            {result && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-6 pt-6 border-t border-slate-100 dark:border-slate-700"
              >
                <h3 className="text-sm font-medium text-slate-900 dark:text-white mb-4">生成结果</h3>

                {/* 续期码 */}
                <div className="bg-slate-50 dark:bg-slate-700/50 rounded-lg p-4 mb-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-slate-500 dark:text-slate-400">续期码</span>
                    <button
                      onClick={() => handleCopy(result.renew_code)}
                      className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 transition-colors"
                    >
                      {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                      {copied ? '已复制' : '复制'}
                    </button>
                  </div>
                  <p className="font-mono text-sm text-slate-900 dark:text-white break-all select-all">
                    {result.renew_code}
                  </p>
                </div>

                {/* 续期时长 */}
                <div className="bg-slate-50 dark:bg-slate-700/50 rounded-lg p-3">
                  <span className="text-xs text-slate-500 dark:text-slate-400 block mb-1">续期时长</span>
                  <span className="text-sm font-medium text-slate-900 dark:text-white">{result.days} 天</span>
                </div>

                {/* 提示 */}
                <div className="mt-4 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-100 dark:border-green-800">
                  <p className="text-xs text-green-700 dark:text-green-300">
                    请复制续期码到启动器的「激活码续期」页面中使用。续期码将在当前激活码的到期时间基础上延长 {result.days} 天。
                  </p>
                </div>
              </motion.div>
            )}
          </div>

          {/* 底部 */}
          <PublicPageFooter />
        </motion.div>
      </div>
    </div>
  )
}
