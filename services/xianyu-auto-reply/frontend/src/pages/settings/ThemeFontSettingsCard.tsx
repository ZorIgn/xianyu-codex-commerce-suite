import { Check, Save, Type } from 'lucide-react'
import { ButtonLoading } from '@/components/common/Loading'
import { cn } from '@/utils/cn'
import { THEME_FONT_OPTIONS, getThemeFontLabel, getThemeFontPreviewStyle } from '@/utils/theme'
import type { ThemeFontFamily, ThemeFontSettings } from '@/types'

interface ThemeFontSettingsCardProps {
  settings: ThemeFontSettings
  saving: boolean
  onChange: (key: keyof ThemeFontSettings, value: ThemeFontFamily) => void
  onSave: () => void
}

export function ThemeFontSettingsCard({ settings, saving, onChange, onSave }: ThemeFontSettingsCardProps) {
  const currentFont = settings['theme.font_family']
  const currentFontOption = THEME_FONT_OPTIONS.find((item) => item.key === currentFont)

  return (
    <div className="vben-card">
      <div className="vben-card-header flex items-center justify-between gap-3">
        <h2 className="vben-card-title">
          <Type className="w-4 h-4" />
          主题字体设置
        </h2>
        <button onClick={onSave} disabled={saving} className="btn-ios-primary">
          {saving ? <ButtonLoading /> : <Save className="w-4 h-4" />}
          保存字体
        </button>
      </div>
      <div className="vben-card-body space-y-4">
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900/60">
          <div className="space-y-2">
            <p className="text-xs text-slate-500 dark:text-slate-400">当前字体</p>
            <h3 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              {getThemeFontLabel(currentFont)}
            </h3>
            <p className="text-sm leading-6 text-slate-600 dark:text-slate-300" style={getThemeFontPreviewStyle(currentFont)}>
              {currentFontOption?.previewText ?? '主题字体预览 Aa 123 你好闲鱼'}
            </p>
            <p className="text-xs leading-5 text-slate-500 dark:text-slate-400">
              {currentFontOption?.description ?? '切换后会同步应用到导航、表格、按钮和登录页等系统界面。'}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-2.5 xl:grid-cols-2">
          {THEME_FONT_OPTIONS.map((option) => {
            const active = option.key === currentFont
            return (
              <button
                key={option.key}
                type="button"
                onClick={() => onChange('theme.font_family', option.key)}
                className={cn(
                  'rounded-xl border p-3 text-left transition-all duration-150',
                  active
                    ? 'border-blue-500 bg-blue-50 shadow-sm dark:bg-blue-900/20'
                    : 'border-slate-200 bg-white hover:border-blue-300 dark:border-slate-700 dark:bg-slate-900/50 dark:hover:border-blue-500'
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1.5">
                    <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{option.label}</p>
                    <p className="text-xs leading-5 text-slate-500 dark:text-slate-400">{option.description}</p>
                    <div
                      className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-950/70 dark:text-slate-200"
                      style={getThemeFontPreviewStyle(option.key)}
                    >
                      {option.previewText}
                    </div>
                  </div>
                  <div className={cn(
                    'mt-0.5 flex h-5 w-5 items-center justify-center rounded-full border',
                    active
                      ? 'border-blue-500 bg-blue-500 text-white'
                      : 'border-slate-300 text-transparent dark:border-slate-600'
                  )}>
                    <Check className="h-3 w-3" />
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
