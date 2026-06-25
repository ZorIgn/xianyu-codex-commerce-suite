import { Check, Palette, Save, Sparkles } from 'lucide-react'
import { ButtonLoading } from '@/components/common/Loading'
import { cn } from '@/utils/cn'
import { THEME_EFFECT_OPTIONS, THEME_PRESET_OPTIONS, getThemeEffectLabel, getThemePreviewStyle } from '@/utils/theme'
import type { ThemeAppearanceSettings, ThemeColorPreset, ThemeEffect } from '@/types'

interface ThemeAppearanceSettingsCardProps {
  settings: ThemeAppearanceSettings
  saving: boolean
  onChange: (key: keyof ThemeAppearanceSettings, value: ThemeEffect | ThemeColorPreset) => void
  onSave: () => void
}

export function ThemeAppearanceSettingsCard({ settings, saving, onChange, onSave }: ThemeAppearanceSettingsCardProps) {
  const currentEffect = settings['theme.effect']
  const currentPreset = settings['theme.color_preset']

  const currentPresetOption = THEME_PRESET_OPTIONS.find((item) => item.key === currentPreset)

  return (
    <div className="vben-card">
      <div className="vben-card-header flex items-center justify-between gap-3">
        <h2 className="vben-card-title">
          <Palette className="w-4 h-4" />
          主题外观设置
        </h2>
        <button onClick={onSave} disabled={saving} className="btn-ios-primary">
          {saving ? <ButtonLoading /> : <Save className="w-4 h-4" />}
          保存外观
        </button>
      </div>
      <div className="vben-card-body space-y-4">
        <div className="relative min-h-[168px] overflow-hidden rounded-2xl border border-slate-200 bg-slate-950 dark:border-slate-700">
          <div className="absolute inset-0" style={getThemePreviewStyle(currentPreset, currentEffect)} />
          <div className="absolute inset-0 bg-slate-950/20 dark:bg-slate-950/35" />
          <div className="relative z-10 p-4 text-white">
            <div className="space-y-2">
              <div className="inline-flex items-center gap-1.5 rounded-full bg-white/15 px-2.5 py-1 text-[11px] font-medium backdrop-blur-sm">
                <Sparkles className="h-3.5 w-3.5" />
                {getThemeEffectLabel(currentEffect)}主题
              </div>
              <div>
                <p className="text-xs text-white/75">当前主题</p>
                <h3 className="mt-1 text-xl font-semibold leading-tight sm:text-2xl">{currentPresetOption?.label ?? '默认主题'}</h3>
              </div>
              <p className="max-w-lg text-xs leading-5 text-white/80 sm:text-sm">
                {currentPresetOption?.description ?? '切换后会同步应用到按钮、导航和登录页等主题区域。'}
              </p>
            </div>
          </div>
        </div>

        <div className="space-y-2.5">
          <div className="grid grid-cols-1 gap-2.5 md:grid-cols-2">
            {THEME_EFFECT_OPTIONS.map((option) => {
              const active = option.value === currentEffect
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => onChange('theme.effect', option.value)}
                  className={cn(
                    'rounded-xl border p-3 text-left transition-all duration-150',
                    active
                      ? 'border-blue-500 bg-blue-50 shadow-sm dark:bg-blue-900/20'
                      : 'border-slate-200 bg-white hover:border-blue-300 dark:border-slate-700 dark:bg-slate-900/50 dark:hover:border-blue-500'
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{option.label}</p>
                      <p className="text-xs leading-5 text-slate-500 dark:text-slate-400">{option.description}</p>
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

        <div className="space-y-2.5">
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
            {THEME_PRESET_OPTIONS.map((preset) => {
              const active = preset.key === currentPreset
              return (
                <button
                  key={preset.key}
                  type="button"
                  onClick={() => onChange('theme.color_preset', preset.key)}
                  className={cn(
                    'overflow-hidden rounded-lg border bg-white text-left transition-all duration-150 dark:bg-slate-900/60',
                    active
                      ? 'border-blue-500 shadow-sm ring-2 ring-blue-200 dark:ring-blue-900/50'
                      : 'border-slate-200 hover:border-blue-300 dark:border-slate-700 dark:hover:border-blue-500'
                  )}
                >
                  <div className="relative h-12 w-full" style={getThemePreviewStyle(preset.key, currentEffect)}>
                    {active && (
                      <div className="absolute right-1.5 top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-blue-500 text-white shadow-sm">
                        <Check className="h-2.5 w-2.5" />
                      </div>
                    )}
                  </div>
                  <div className="p-2.5">
                    <div className="truncate text-xs font-semibold text-slate-900 dark:text-slate-100">{preset.label}</div>
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
