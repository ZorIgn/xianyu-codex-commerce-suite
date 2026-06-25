/**
 * 获取激活码页面（公开页面，无需登录）
 *
 * 功能：
 * 1. 输入机器码（32位十六进制）
 * 2. 点击按钮生成试用激活码（默认15天）
 * 3. 显示激活码、到期时间，支持一键复制
 */
import { useState } from 'react'
import { motion } from 'framer-motion'
import { Key, Copy, Check, History, ChevronLeft, ChevronRight } from 'lucide-react'
import { generateTrialActivation, getActivationHistory, type ActivationResult, type ActivationHistoryRecord } from '@/api/activation'
import { useUIStore } from '@/store/uiStore'
import { AuthNavbar, PublicPageFooter } from '@/components/common/AuthNavbar'
import { ButtonLoading } from '@/components/common/Loading'

export function GetActivation() {
  const { addToast } = useUIStore()
  const [machineId, setMachineId] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ActivationResult | null>(null)
  const [copied, setCopied] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyRecords, setHistoryRecords] = useState<ActivationHistoryRecord[]>([])
  const [historyPage, setHistoryPage] = useState(1)
  const [historyTotal, setHistoryTotal] = useState(0)
  const [historyTotalPages, setHistoryTotalPages] = useState(0)

  /** 校验机器码格式 */
  const validateMachineId = (id: string): string | null => {
    const trimmed = id.trim().toUpperCase()
    if (!trimmed) return '请输入机器码'
    if (trimmed.length !== 32) return `机器码长度应为32位，当前${trimmed.length}位`
    if (!/^[0-9A-F]{32}$/.test(trimmed)) return '机器码应为十六进制字符串（0-9, A-F）'
    return null
  }

  /** 提交生成激活码 */
  const handleGenerate = async () => {
    const error = validateMachineId(machineId)
    if (error) {
      addToast({ type: 'error', message: error })
      return
    }

    setLoading(true)
    setResult(null)
    try {
      const resp = await generateTrialActivation(machineId.trim().toUpperCase())
      if (resp.success && resp.data) {
        setResult(resp.data)
        addToast({ type: 'success', message: '激活码生成成功' })
      } else {
        addToast({ type: 'error', message: resp.message || '生成失败' })
      }
    } catch {
      addToast({ type: 'error', message: '请求失败，请检查网络连接' })
    } finally {
      setLoading(false)
    }
  }

  /** 复制激活码到剪贴板 */
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

  /** 查询历史记录 */
  const handleQueryHistory = async (page: number = 1) => {
    const error = validateMachineId(machineId)
    if (error) {
      addToast({ type: 'error', message: error })
      return
    }

    setHistoryLoading(true)
    try {
      const resp = await getActivationHistory(machineId.trim().toUpperCase(), page, 10)
      if (resp.success && resp.data) {
        setHistoryRecords(resp.data.records)
        setHistoryTotal(resp.data.total)
        setHistoryPage(resp.data.page)
        setHistoryTotalPages(resp.data.total_pages)
        setShowHistory(true)
      } else {
        addToast({ type: 'error', message: resp.message || '查询失败' })
      }
    } catch {
      addToast({ type: 'error', message: '请求失败，请检查网络连接' })
    } finally {
      setHistoryLoading(false)
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
            <div className="w-14 h-14 rounded-xl bg-blue-500 text-white mx-auto mb-4 flex items-center justify-center">
              <Key className="w-7 h-7" />
            </div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">获取激活码</h1>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">
              输入机器码，获取 <span className="text-blue-600 dark:text-blue-400 font-medium">15天</span> 试用激活码
            </p>
          </div>

          {/* 表单卡片 */}
          <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 p-5 sm:p-8">
            <div className="space-y-4">
              {/* 机器码输入 */}
              <div className="input-group">
                <label className="input-label">机器码</label>
                <div className="relative">
                  <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
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

              {/* 按钮组 */}
              <div className="flex gap-3">
                <button
                  onClick={handleGenerate}
                  disabled={loading}
                  className="flex-1 btn-ios-primary"
                >
                  {loading ? <ButtonLoading /> : '生成激活码'}
                </button>
                <button
                  onClick={() => handleQueryHistory(1)}
                  disabled={historyLoading}
                  className="flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg
                             bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-200
                             hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors
                             disabled:opacity-50 disabled:cursor-not-allowed"
                  title="查询历史记录"
                >
                  {historyLoading ? <ButtonLoading /> : <><History className="w-4 h-4" />历史</>}
                </button>
              </div>
            </div>

            {/* 结果展示 */}
            {result && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-6 pt-6 border-t border-slate-100 dark:border-slate-700"
              >
                <h3 className="text-sm font-medium text-slate-900 dark:text-white mb-4">生成结果</h3>

                {/* 激活码 */}
                <div className="bg-slate-50 dark:bg-slate-700/50 rounded-lg p-4 mb-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-slate-500 dark:text-slate-400">激活码</span>
                    <button
                      onClick={() => handleCopy(result.activation_code)}
                      className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 transition-colors"
                    >
                      {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                      {copied ? '已复制' : '复制'}
                    </button>
                  </div>
                  <p className="font-mono text-sm text-slate-900 dark:text-white break-all select-all">
                    {result.activation_code}
                  </p>
                </div>

                {/* 其他信息 */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-slate-50 dark:bg-slate-700/50 rounded-lg p-3">
                    <span className="text-xs text-slate-500 dark:text-slate-400 block mb-1">有效期</span>
                    <span className="text-sm font-medium text-slate-900 dark:text-white">{result.days} 天</span>
                  </div>
                  <div className="bg-slate-50 dark:bg-slate-700/50 rounded-lg p-3">
                    <span className="text-xs text-slate-500 dark:text-slate-400 block mb-1">到期时间</span>
                    <span className="text-sm font-medium text-slate-900 dark:text-white">{result.expire_time}</span>
                  </div>
                </div>

                {/* 提示 */}
                <div className="mt-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-100 dark:border-blue-800">
                  <p className="text-xs text-blue-700 dark:text-blue-300">
                    请复制激活码到启动器中激活使用。每个机器码可以多次获取试用激活码，但每次生成的激活码有效期均为 {result.days} 天。
                  </p>
                </div>
              </motion.div>
            )}

            {/* 历史记录展示 */}
            {showHistory && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-6 pt-6 border-t border-slate-100 dark:border-slate-700"
              >
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-medium text-slate-900 dark:text-white">
                    历史记录 <span className="text-slate-400 dark:text-slate-500 font-normal">({historyTotal}条)</span>
                  </h3>
                  <button
                    onClick={() => setShowHistory(false)}
                    className="text-xs text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                  >
                    收起
                  </button>
                </div>

                {historyRecords.length === 0 ? (
                  <div className="text-center py-8 text-slate-400 dark:text-slate-500 text-sm">
                    暂无历史记录
                  </div>
                ) : (
                  <>
                    <div className="space-y-2">
                      {historyRecords.map((record) => (
                        <div
                          key={record.id}
                          className="bg-slate-50 dark:bg-slate-700/50 rounded-lg p-3"
                        >
                          <div className="flex items-center justify-between mb-2">
                            <span className={`text-xs px-2 py-0.5 rounded ${
                              record.code_type === 'generate'
                                ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                                : 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
                            }`}>
                              {record.code_type_name}
                            </span>
                            <span className="text-xs text-slate-400 dark:text-slate-500">
                              {record.created_at}
                            </span>
                          </div>
                          <p className="font-mono text-xs text-slate-700 dark:text-slate-300 break-all select-all">
                            {record.generated_code}
                          </p>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2 text-xs text-slate-400 dark:text-slate-500">
                            <span>有效期: {record.days}天</span>
                            <span>到期时间: {record.expire_time || '不适用'}</span>
                            <span>
                              到期状态:
                              <span className={`ml-1 inline-flex items-center rounded px-1.5 py-0.5 ${
                                record.expire_status === '未到期'
                                  ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300'
                                  : record.expire_status === '已到期'
                                    ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
                                    : 'bg-slate-200 text-slate-700 dark:bg-slate-600 dark:text-slate-200'
                              }`}>
                                {record.expire_status}
                              </span>
                            </span>
                            <span>IP: {record.ip_address}</span>
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* 分页 */}
                    {historyTotalPages > 1 && (
                      <div className="flex items-center justify-center gap-2 mt-4">
                        <button
                          onClick={() => handleQueryHistory(historyPage - 1)}
                          disabled={historyPage <= 1 || historyLoading}
                          className="p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          <ChevronLeft className="w-4 h-4 text-slate-600 dark:text-slate-400" />
                        </button>
                        <span className="text-sm text-slate-600 dark:text-slate-400">
                          {historyPage} / {historyTotalPages}
                        </span>
                        <button
                          onClick={() => handleQueryHistory(historyPage + 1)}
                          disabled={historyPage >= historyTotalPages || historyLoading}
                          className="p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          <ChevronRight className="w-4 h-4 text-slate-600 dark:text-slate-400" />
                        </button>
                      </div>
                    )}
                  </>
                )}
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
