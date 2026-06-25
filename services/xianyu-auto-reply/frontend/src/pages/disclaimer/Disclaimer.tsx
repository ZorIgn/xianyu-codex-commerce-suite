/**
 * 免责声明页面
 * 
 * 展示系统免责声明内容，与登录弹窗使用相同的内容
 */
import { useEffect, useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import { getSystemSettings, normalizeDisclaimerSettings } from '@/api/settings'
import { PageLoading } from '@/components/common/Loading'
import { SystemDisclaimerContent } from '@/components/common/SystemDisclaimerContent'
import { useUIStore } from '@/store/uiStore'
import { cn } from '@/utils/cn'
import { getApiErrorMessage } from '@/utils/apiError'
import type { DisclaimerSettings } from '@/types'

export function Disclaimer() {
  const { addToast } = useUIStore()
  const [loading, setLoading] = useState(true)
  const [settings, setSettings] = useState<DisclaimerSettings>(() => normalizeDisclaimerSettings())

  useEffect(() => {
    const loadSettings = async () => {
      try {
        setLoading(true)
        const result = await getSystemSettings()
        if (result.success && result.data) {
          setSettings(normalizeDisclaimerSettings(result.data))
        }
      } catch (error) {
        addToast({ type: 'error', message: getApiErrorMessage(error, '加载免责声明失败') })
      } finally {
        setLoading(false)
      }
    }

    loadSettings()
  }, [addToast])

  if (loading) {
    return <PageLoading />
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* 页面标题 */}
      <div className="flex items-center gap-3 mb-6">
        <AlertTriangle className="w-8 h-8 text-amber-500" />
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">
          {settings['disclaimer.title']}
        </h1>
      </div>

      {/* 内容卡片 */}
      <div className={cn(
        'bg-white dark:bg-slate-800 rounded-xl shadow-sm',
        'border border-slate-200 dark:border-slate-700',
        'p-6'
      )}>
        <SystemDisclaimerContent content={settings['disclaimer.content']} />
      </div>
    </div>
  )
}
