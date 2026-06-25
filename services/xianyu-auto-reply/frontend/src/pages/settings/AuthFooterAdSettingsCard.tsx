import { Megaphone, Save } from 'lucide-react'
import { ButtonLoading } from '@/components/common/Loading'
import { SafeHtml } from '@/components/common/SafeHtml'
import type { AuthFooterAdSettings } from '@/types'

interface AuthFooterAdSettingsCardProps {
  settings: AuthFooterAdSettings
  saving: boolean
  onChange: (key: keyof AuthFooterAdSettings, value: string) => void
  onSave: () => void
}

export function AuthFooterAdSettingsCard({ settings, saving, onChange, onSave }: AuthFooterAdSettingsCardProps) {
  return (
    <div className="vben-card">
      <div className="vben-card-header flex items-center justify-between gap-3">
        <h2 className="vben-card-title">
          <Megaphone className="w-4 h-4 text-blue-500" />
          底部广告设置
        </h2>
        <button onClick={onSave} disabled={saving} className="btn-ios-primary">
          {saving ? <ButtonLoading /> : <Save className="w-4 h-4" />}
          保存
        </button>
      </div>
      <div className="vben-card-body space-y-4">
        <p className="text-sm text-slate-500 dark:text-slate-400">
          这里的内容会展示在登录页和注册页底部，支持输入 HTML 标签。系统会在前端渲染时自动过滤脚本和危险属性。
        </p>

        <div className="input-group">
          <label className="input-label">底部广告 HTML</label>
          <textarea
            value={settings['auth.footer_ad_html']}
            onChange={(event) => onChange('auth.footer_ad_html', event.target.value)}
            placeholder="请输入底部广告 HTML"
            rows={5}
            className="input-ios min-h-[132px] resize-y"
          />
        </div>

        <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/60 p-4 space-y-3">
          <p className="text-sm font-medium text-slate-700 dark:text-slate-300">登录/注册页底部预览</p>
          <div className="rounded-xl border border-dashed border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900/70 px-4 py-3">
            <SafeHtml
              html={settings['auth.footer_ad_html']}
              className="text-center text-xs text-slate-400 dark:text-slate-500"
            />
          </div>
        </div>
      </div>
    </div>
  )
}
