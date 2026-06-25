import type { CSSProperties } from 'react'
import type {
  SystemSettings,
  ThemeAppearanceSettings,
  ThemeColorPreset,
  ThemeEffect,
  ThemeFontFamily,
  ThemeFontSettings,
  ThemeSettings,
} from '@/types'

interface ThemePalette {
  50: string
  100: string
  200: string
  300: string
  400: string
  500: string
  600: string
  700: string
  800: string
  900: string
  gradientFrom: string
  gradientVia: string
  gradientTo: string
}

interface ThemePresetMeta {
  key: ThemeColorPreset
  label: string
  description: string
  category: 'pure' | 'colorful'
  recommendedEffect: ThemeEffect
  palette: ThemePalette
}

interface ThemeFontMeta {
  key: ThemeFontFamily
  label: string
  description: string
  previewText: string
  fontFamily: string
}

type ThemeSettingsSource = Partial<SystemSettings> | null | undefined

export type ThemeMode = 'light' | 'dark'

export const THEME_SETTINGS_UPDATED_EVENT = 'theme-settings-updated'
export const THEME_MODE_STORAGE_KEY = 'theme'

const DEFAULT_THEME_SETTINGS: ThemeSettings = {
  'theme.effect': 'solid',
  'theme.color_preset': 'ocean',
  'theme.font_family': 'system',
}

const THEME_PRESETS: Record<ThemeColorPreset, ThemePresetMeta> = {
  ocean: {
    key: 'ocean',
    label: '海洋蓝',
    description: '经典蓝白风格，清爽稳定，适合系统默认主题。',
    category: 'pure',
    recommendedEffect: 'solid',
    palette: {
      50: '239 246 255',
      100: '219 234 254',
      200: '191 219 254',
      300: '147 197 253',
      400: '96 165 250',
      500: '59 130 246',
      600: '37 99 235',
      700: '29 78 216',
      800: '30 64 175',
      900: '30 58 138',
      gradientFrom: '37 99 235',
      gradientVia: '59 130 246',
      gradientTo: '14 165 233',
    },
  },
  emerald: {
    key: 'emerald',
    label: '翡翠绿',
    description: '纯色偏商务，按钮和选中态更柔和自然。',
    category: 'pure',
    recommendedEffect: 'solid',
    palette: {
      50: '236 253 245',
      100: '209 250 229',
      200: '167 243 208',
      300: '110 231 183',
      400: '52 211 153',
      500: '16 185 129',
      600: '5 150 105',
      700: '4 120 87',
      800: '6 95 70',
      900: '6 78 59',
      gradientFrom: '16 185 129',
      gradientVia: '34 197 94',
      gradientTo: '59 130 246',
    },
  },
  violet: {
    key: 'violet',
    label: '雾感紫',
    description: '纯色偏高级，适合偏内容型和管理型界面。',
    category: 'pure',
    recommendedEffect: 'solid',
    palette: {
      50: '245 243 255',
      100: '237 233 254',
      200: '221 214 254',
      300: '196 181 253',
      400: '167 139 250',
      500: '139 92 246',
      600: '124 58 237',
      700: '109 40 217',
      800: '91 33 182',
      900: '76 29 149',
      gradientFrom: '124 58 237',
      gradientVia: '139 92 246',
      gradientTo: '236 72 153',
    },
  },
  indigo: {
    key: 'indigo',
    label: '深海靛蓝',
    description: '蓝紫之间更稳重，适合偏专业、偏管理的后台场景。',
    category: 'pure',
    recommendedEffect: 'solid',
    palette: { 50: '238 242 255', 100: '224 231 255', 200: '199 210 254', 300: '165 180 252', 400: '129 140 248', 500: '99 102 241', 600: '79 70 229', 700: '67 56 202', 800: '55 48 163', 900: '49 46 129', gradientFrom: '79 70 229', gradientVia: '129 140 248', gradientTo: '59 130 246' },
  },
  amber: {
    key: 'amber',
    label: '琥珀金',
    description: '暖金色更醒目，适合强调重点按钮和数据亮点。',
    category: 'pure',
    recommendedEffect: 'solid',
    palette: { 50: '255 251 235', 100: '254 243 199', 200: '253 230 138', 300: '252 211 77', 400: '251 191 36', 500: '245 158 11', 600: '217 119 6', 700: '180 83 9', 800: '146 64 14', 900: '120 53 15', gradientFrom: '245 158 11', gradientVia: '251 191 36', gradientTo: '249 115 22' },
  },
  sunset: {
    key: 'sunset',
    label: '落日橙',
    description: '偏暖色的炫彩风格，强调按钮和卡片视觉冲击。',
    category: 'colorful',
    recommendedEffect: 'gradient',
    palette: {
      50: '255 247 237',
      100: '255 237 213',
      200: '254 215 170',
      300: '253 186 116',
      400: '251 146 60',
      500: '249 115 22',
      600: '234 88 12',
      700: '194 65 12',
      800: '154 52 18',
      900: '124 45 18',
      gradientFrom: '249 115 22',
      gradientVia: '236 72 153',
      gradientTo: '168 85 247',
    },
  },
  aurora: {
    key: 'aurora',
    label: '极光青',
    description: '青绿到紫色的炫彩过渡，科技感更强。',
    category: 'colorful',
    recommendedEffect: 'gradient',
    palette: {
      50: '240 253 250',
      100: '204 251 241',
      200: '153 246 228',
      300: '94 234 212',
      400: '45 212 191',
      500: '20 184 166',
      600: '13 148 136',
      700: '14 116 144',
      800: '21 94 117',
      900: '22 78 99',
      gradientFrom: '34 211 238',
      gradientVia: '16 185 129',
      gradientTo: '168 85 247',
    },
  },
  rose: {
    key: 'rose',
    label: '霓虹粉',
    description: '粉紫暖调的炫彩主题，更适合营销和活动氛围。',
    category: 'colorful',
    recommendedEffect: 'gradient',
    palette: {
      50: '255 241 242',
      100: '255 228 230',
      200: '254 205 211',
      300: '253 164 175',
      400: '251 113 133',
      500: '244 63 94',
      600: '225 29 72',
      700: '190 24 93',
      800: '159 18 57',
      900: '136 19 55',
      gradientFrom: '244 63 94',
      gradientVia: '236 72 153',
      gradientTo: '251 146 60',
    },
  },
  ruby: {
    key: 'ruby',
    label: '宝石红',
    description: '更强烈的红紫氛围，适合活动、推广和高对比视觉场景。',
    category: 'colorful',
    recommendedEffect: 'gradient',
    palette: { 50: '254 242 242', 100: '254 226 226', 200: '254 202 202', 300: '252 165 165', 400: '248 113 113', 500: '239 68 68', 600: '220 38 38', 700: '185 28 28', 800: '153 27 27', 900: '127 29 29', gradientFrom: '220 38 38', gradientVia: '244 63 94', gradientTo: '168 85 247' },
  },
}

const THEME_FONT_FAMILIES: Record<ThemeFontFamily, ThemeFontMeta> = {
  system: {
    key: 'system',
    label: '系统默认',
    description: '优先使用当前设备系统字体，兼顾中文显示与跨平台一致性。',
    previewText: '系统默认 Aa 字体示例 123 你好闲鱼',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif',
  },
  yahei: {
    key: 'yahei',
    label: '微软雅黑',
    description: 'Windows 环境更常见，表格和后台场景下识别度较高。',
    previewText: '微软雅黑 Aa 字体示例 123 你好闲鱼',
    fontFamily: '"Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif',
  },
  heiti: {
    key: 'heiti',
    label: '现代黑体',
    description: '笔画利落、风格现代，适合强调清晰感的系统界面。',
    previewText: '现代黑体 Aa 字体示例 123 你好闲鱼',
    fontFamily: '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans CJK SC", "Segoe UI", sans-serif',
  },
  songti: {
    key: 'songti',
    label: '雅致宋体',
    description: '更适合偏内容阅读型页面，让标题和正文层次更明显。',
    previewText: '雅致宋体 Aa 字体示例 123 你好闲鱼',
    fontFamily: '"Songti SC", "STSong", "SimSun", "Noto Serif CJK SC", serif',
  },
  kaiti: {
    key: 'kaiti',
    label: '经典楷体',
    description: '书卷气更强，适合标题、说明区和需要文化感的界面。',
    previewText: '经典楷体 Aa 字体示例 123 你好闲鱼',
    fontFamily: '"KaiTi", "楷体", "STKaiti", "Kaiti SC", serif',
  },
  fangsong: {
    key: 'fangsong',
    label: '文雅仿宋',
    description: '阅读感柔和，适合说明文案、公告和偏正文型页面。',
    previewText: '文雅仿宋 Aa 字体示例 123 你好闲鱼',
    fontFamily: '"FangSong", "仿宋", "STFangsong", "FZFangSong-Z02", serif',
  },
  xingkai: {
    key: 'xingkai',
    label: '行楷风格',
    description: '带一点书写感，适合欢迎页、标题区和偏个性化的系统界面。',
    previewText: '行楷风格 Aa 字体示例 123 你好闲鱼',
    fontFamily: '"STXingkai", "华文行楷", "KaiTi", "楷体", "STKaiti", "Kaiti SC", serif',
  },
  rounded: {
    key: 'rounded',
    label: '圆润字体',
    description: '字形更圆润友好，适合轻量化、现代化和移动端风格界面。',
    previewText: '圆润字体 Aa 字体示例 123 你好闲鱼',
    fontFamily: '"SF Pro Rounded", "Arial Rounded MT Bold", "Helvetica Rounded", "PingFang SC", "Microsoft YaHei", sans-serif',
  },
  monospace: {
    key: 'monospace',
    label: '等宽风格',
    description: '数字与字符更容易对齐，适合数据较多或技术风格界面。',
    previewText: '等宽风格 Aa 字体示例 123 你好闲鱼',
    fontFamily: '"Cascadia Code", "JetBrains Mono", "Microsoft YaHei Mono", "Consolas", "Microsoft YaHei", monospace',
  },
}

const THEME_EFFECT_LABELS: Record<ThemeEffect, string> = {
  solid: '纯色',
  gradient: '炫彩',
}

const THEME_EFFECT_DESCRIPTIONS: Record<ThemeEffect, string> = {
  solid: '保持系统整体干净统一，强调清晰度和稳定性。',
  gradient: '在按钮、顶部区域和背景氛围中增加炫彩渐变效果。',
}

const isThemeEffect = (value: unknown): value is ThemeEffect => value === 'solid' || value === 'gradient'

const isThemeColorPreset = (value: unknown): value is ThemeColorPreset => {
  return value === 'ocean' || value === 'emerald' || value === 'violet' || value === 'indigo' || value === 'amber' || value === 'sunset' || value === 'aurora' || value === 'rose' || value === 'ruby'
}

const isThemeFontFamily = (value: unknown): value is ThemeFontFamily => {
  return value === 'system' || value === 'yahei' || value === 'heiti' || value === 'songti' || value === 'kaiti' || value === 'fangsong' || value === 'xingkai' || value === 'rounded' || value === 'monospace'
}

const setCssVariable = (name: string, value: string) => {
  document.documentElement.style.setProperty(name, value)
}

const rgb = (value: string, alpha?: number) => {
  if (typeof alpha === 'number') {
    return `rgb(${value} / ${alpha})`
  }
  return `rgb(${value})`
}

export const THEME_PRESET_OPTIONS = Object.values(THEME_PRESETS)
export const THEME_FONT_OPTIONS = Object.values(THEME_FONT_FAMILIES)

export const THEME_EFFECT_OPTIONS = Object.entries(THEME_EFFECT_LABELS).map(([value, label]) => ({
  value: value as ThemeEffect,
  label,
  description: THEME_EFFECT_DESCRIPTIONS[value as ThemeEffect],
}))

export const getThemePresetMeta = (preset: ThemeColorPreset): ThemePresetMeta => {
  return THEME_PRESETS[preset]
}

export const getThemeEffectLabel = (effect: ThemeEffect): string => {
  return THEME_EFFECT_LABELS[effect]
}

export const getThemeFontMeta = (fontFamily: ThemeFontFamily): ThemeFontMeta => {
  return THEME_FONT_FAMILIES[fontFamily]
}

export const getThemeFontLabel = (fontFamily: ThemeFontFamily): string => {
  return THEME_FONT_FAMILIES[fontFamily].label
}

export const getThemeFontPreviewStyle = (fontFamily: ThemeFontFamily): CSSProperties => {
  return {
    fontFamily: getThemeFontMeta(fontFamily).fontFamily,
  }
}

export const normalizeThemeAppearanceSettings = (settings?: ThemeSettingsSource): ThemeAppearanceSettings => {
  const effect = settings?.['theme.effect']
  const colorPreset = settings?.['theme.color_preset']

  return {
    'theme.effect': isThemeEffect(effect) ? effect : DEFAULT_THEME_SETTINGS['theme.effect'],
    'theme.color_preset': isThemeColorPreset(colorPreset) ? colorPreset : DEFAULT_THEME_SETTINGS['theme.color_preset'],
  }
}

export const normalizeThemeFontSettings = (settings?: ThemeSettingsSource): ThemeFontSettings => {
  const fontFamily = settings?.['theme.font_family']

  return {
    'theme.font_family': isThemeFontFamily(fontFamily) ? fontFamily : DEFAULT_THEME_SETTINGS['theme.font_family'],
  }
}

export const normalizeThemeSettings = (settings?: ThemeSettingsSource): ThemeSettings => {
  return {
    ...normalizeThemeAppearanceSettings(settings),
    ...normalizeThemeFontSettings(settings),
  }
}

export const getThemePreviewStyle = (preset: ThemeColorPreset, effect: ThemeEffect): CSSProperties => {
  const palette = getThemePresetMeta(preset).palette

  if (effect === 'gradient') {
    return {
      backgroundImage: `linear-gradient(135deg, ${rgb(palette.gradientFrom)} 0%, ${rgb(palette.gradientVia)} 50%, ${rgb(palette.gradientTo)} 100%)`,
    }
  }

  return {
    backgroundImage: `linear-gradient(135deg, ${rgb(palette[600])} 0%, ${rgb(palette[500])} 100%)`,
  }
}

export const applyThemeSettings = (settings?: ThemeSettingsSource): ThemeSettings => {
  const normalized = normalizeThemeSettings(settings)

  if (typeof document === 'undefined') {
    return normalized
  }

  const root = document.documentElement
  const preset = THEME_PRESETS[normalized['theme.color_preset']]
  const font = THEME_FONT_FAMILIES[normalized['theme.font_family']]
  const { palette } = preset

  root.dataset.themeEffect = normalized['theme.effect']
  root.dataset.themeColorPreset = normalized['theme.color_preset']
  root.dataset.themeFontFamily = normalized['theme.font_family']

  setCssVariable('--theme-primary-50', palette[50])
  setCssVariable('--theme-primary-100', palette[100])
  setCssVariable('--theme-primary-200', palette[200])
  setCssVariable('--theme-primary-300', palette[300])
  setCssVariable('--theme-primary-400', palette[400])
  setCssVariable('--theme-primary-500', palette[500])
  setCssVariable('--theme-primary-600', palette[600])
  setCssVariable('--theme-primary-700', palette[700])
  setCssVariable('--theme-primary-800', palette[800])
  setCssVariable('--theme-primary-900', palette[900])
  setCssVariable('--theme-gradient-from', palette.gradientFrom)
  setCssVariable('--theme-gradient-via', palette.gradientVia)
  setCssVariable('--theme-gradient-to', palette.gradientTo)
  setCssVariable('--color-primary', palette[500])
  setCssVariable('--color-primary-hover', palette[600])
  setCssVariable('--color-primary-light', palette[100])
  setCssVariable('--theme-font-family', font.fontFamily)

  return normalized
}

const getSystemPreferredThemeMode = (): ThemeMode => {
  if (typeof window === 'undefined') {
    return 'light'
  }

  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

const getStoredThemeMode = (): ThemeMode | null => {
  if (typeof window === 'undefined') {
    return null
  }

  const storedMode = window.localStorage.getItem(THEME_MODE_STORAGE_KEY)
  return storedMode === 'dark' || storedMode === 'light' ? storedMode : null
}

export const getCurrentThemeMode = (): ThemeMode => {
  if (typeof document === 'undefined') {
    return 'light'
  }

  return document.documentElement.classList.contains('dark') ? 'dark' : 'light'
}

export const applyThemeMode = (mode: ThemeMode): ThemeMode => {
  if (typeof document === 'undefined' || typeof window === 'undefined') {
    return mode
  }

  document.documentElement.classList.toggle('dark', mode === 'dark')
  window.localStorage.setItem(THEME_MODE_STORAGE_KEY, mode)
  return mode
}

export const initializeThemeMode = (): ThemeMode => {
  const mode = getStoredThemeMode() ?? getSystemPreferredThemeMode()
  return applyThemeMode(mode)
}

export const toggleThemeMode = (): ThemeMode => {
  return applyThemeMode(getCurrentThemeMode() === 'dark' ? 'light' : 'dark')
}

export const dispatchThemeSettingsUpdated = (settings?: ThemeSettingsSource): void => {
  if (typeof window === 'undefined') {
    return
  }

  const normalized = applyThemeSettings(settings)
  window.dispatchEvent(new CustomEvent<ThemeSettings>(THEME_SETTINGS_UPDATED_EVENT, { detail: normalized }))
}
