/**
 * 推广返佣系统 - 主题工具
 *
 * 复用主系统的主题颜色和字体设置，从后端读取xy_system_settings中的主题参数，
 * 通过CSS变量动态应用到页面，与主系统保持一致的外观。
 *
 * 主题参数：
 * - theme.effect: 纯色(solid) / 炫彩(gradient)
 * - theme.color_preset: 颜色预设（ocean/emerald/violet等）
 * - theme.font_family: 字体预设（system/yahei/heiti等）
 */

/** 颜色预设类型 */
type ThemeColorPreset = 'ocean' | 'emerald' | 'violet' | 'indigo' | 'amber' | 'sunset' | 'aurora' | 'rose' | 'ruby'

/** 主题效果类型 */
type ThemeEffect = 'solid' | 'gradient'

/** 字体预设类型 */
type ThemeFontFamily = 'system' | 'yahei' | 'heiti' | 'songti' | 'kaiti' | 'fangsong' | 'xingkai' | 'rounded' | 'monospace'

/** 主题设置 */
interface ThemeSettings {
  'theme.effect': ThemeEffect
  'theme.color_preset': ThemeColorPreset
  'theme.font_family': ThemeFontFamily
}

/** 调色板 */
interface ThemePalette {
  50: string; 100: string; 200: string; 300: string; 400: string
  500: string; 600: string; 700: string; 800: string; 900: string
  gradientFrom: string; gradientVia: string; gradientTo: string
}

/** 颜色预设数据 */
const THEME_PALETTES: Record<ThemeColorPreset, ThemePalette> = {
  ocean: { 50: '239 246 255', 100: '219 234 254', 200: '191 219 254', 300: '147 197 253', 400: '96 165 250', 500: '59 130 246', 600: '37 99 235', 700: '29 78 216', 800: '30 64 175', 900: '30 58 138', gradientFrom: '37 99 235', gradientVia: '59 130 246', gradientTo: '14 165 233' },
  emerald: { 50: '236 253 245', 100: '209 250 229', 200: '167 243 208', 300: '110 231 183', 400: '52 211 153', 500: '16 185 129', 600: '5 150 105', 700: '4 120 87', 800: '6 95 70', 900: '6 78 59', gradientFrom: '16 185 129', gradientVia: '34 197 94', gradientTo: '59 130 246' },
  violet: { 50: '245 243 255', 100: '237 233 254', 200: '221 214 254', 300: '196 181 253', 400: '167 139 250', 500: '139 92 246', 600: '124 58 237', 700: '109 40 217', 800: '91 33 182', 900: '76 29 149', gradientFrom: '124 58 237', gradientVia: '139 92 246', gradientTo: '236 72 153' },
  indigo: { 50: '238 242 255', 100: '224 231 255', 200: '199 210 254', 300: '165 180 252', 400: '129 140 248', 500: '99 102 241', 600: '79 70 229', 700: '67 56 202', 800: '55 48 163', 900: '49 46 129', gradientFrom: '79 70 229', gradientVia: '129 140 248', gradientTo: '59 130 246' },
  amber: { 50: '255 251 235', 100: '254 243 199', 200: '253 230 138', 300: '252 211 77', 400: '251 191 36', 500: '245 158 11', 600: '217 119 6', 700: '180 83 9', 800: '146 64 14', 900: '120 53 15', gradientFrom: '245 158 11', gradientVia: '251 191 36', gradientTo: '249 115 22' },
  sunset: { 50: '255 247 237', 100: '255 237 213', 200: '254 215 170', 300: '253 186 116', 400: '251 146 60', 500: '249 115 22', 600: '234 88 12', 700: '194 65 12', 800: '154 52 18', 900: '124 45 18', gradientFrom: '249 115 22', gradientVia: '236 72 153', gradientTo: '168 85 247' },
  aurora: { 50: '240 253 250', 100: '204 251 241', 200: '153 246 228', 300: '94 234 212', 400: '45 212 191', 500: '20 184 166', 600: '13 148 136', 700: '14 116 144', 800: '21 94 117', 900: '22 78 99', gradientFrom: '34 211 238', gradientVia: '16 185 129', gradientTo: '168 85 247' },
  rose: { 50: '255 241 242', 100: '255 228 230', 200: '254 205 211', 300: '253 164 175', 400: '251 113 133', 500: '244 63 94', 600: '225 29 72', 700: '190 24 93', 800: '159 18 57', 900: '136 19 55', gradientFrom: '244 63 94', gradientVia: '236 72 153', gradientTo: '251 146 60' },
  ruby: { 50: '254 242 242', 100: '254 226 226', 200: '254 202 202', 300: '252 165 165', 400: '248 113 113', 500: '239 68 68', 600: '220 38 38', 700: '185 28 28', 800: '153 27 27', 900: '127 29 29', gradientFrom: '220 38 38', gradientVia: '244 63 94', gradientTo: '168 85 247' },
}

/** 字体预设数据 */
const THEME_FONTS: Record<ThemeFontFamily, string> = {
  system: '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif',
  yahei: '"Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif',
  heiti: '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans CJK SC", "Segoe UI", sans-serif',
  songti: '"Songti SC", "STSong", "SimSun", "Noto Serif CJK SC", serif',
  kaiti: '"KaiTi", "楷体", "STKaiti", "Kaiti SC", serif',
  fangsong: '"FangSong", "仿宋", "STFangsong", "FZFangSong-Z02", serif',
  xingkai: '"STXingkai", "华文行楷", "KaiTi", "楷体", "STKaiti", "Kaiti SC", serif',
  rounded: '"SF Pro Rounded", "Arial Rounded MT Bold", "Helvetica Rounded", "PingFang SC", "Microsoft YaHei", sans-serif',
  monospace: '"Cascadia Code", "JetBrains Mono", "Microsoft YaHei Mono", "Consolas", "Microsoft YaHei", monospace',
}

/** 默认主题设置 */
const DEFAULT_THEME: ThemeSettings = {
  'theme.effect': 'solid',
  'theme.color_preset': 'ocean',
  'theme.font_family': 'system',
}

/** 校验颜色预设值 */
const isValidPreset = (v: unknown): v is ThemeColorPreset =>
  typeof v === 'string' && v in THEME_PALETTES

/** 校验效果值 */
const isValidEffect = (v: unknown): v is ThemeEffect =>
  v === 'solid' || v === 'gradient'

/** 校验字体值 */
const isValidFont = (v: unknown): v is ThemeFontFamily =>
  typeof v === 'string' && v in THEME_FONTS

/** 设置CSS变量 */
const setCssVar = (name: string, value: string) => {
  document.documentElement.style.setProperty(name, value)
}

/**
 * 标准化主题设置，确保所有值合法
 */
export const normalizeThemeSettings = (raw?: Record<string, unknown> | null): ThemeSettings => {
  const effect = raw?.['theme.effect']
  const preset = raw?.['theme.color_preset']
  const font = raw?.['theme.font_family']

  return {
    'theme.effect': isValidEffect(effect) ? effect : DEFAULT_THEME['theme.effect'],
    'theme.color_preset': isValidPreset(preset) ? preset : DEFAULT_THEME['theme.color_preset'],
    'theme.font_family': isValidFont(font) ? font : DEFAULT_THEME['theme.font_family'],
  }
}

/**
 * 将主题设置应用到DOM（设置CSS变量和data属性）
 *
 * 与主系统的 applyThemeSettings 保持完全一致的CSS变量名
 */
export const applyThemeSettings = (raw?: Record<string, unknown> | null): ThemeSettings => {
  const settings = normalizeThemeSettings(raw)

  if (typeof document === 'undefined') return settings

  const root = document.documentElement
  const palette = THEME_PALETTES[settings['theme.color_preset']]
  const fontFamily = THEME_FONTS[settings['theme.font_family']]

  // 设置data属性（供CSS选择器使用）
  root.dataset.themeEffect = settings['theme.effect']
  root.dataset.themeColorPreset = settings['theme.color_preset']
  root.dataset.themeFontFamily = settings['theme.font_family']

  // 设置颜色CSS变量
  setCssVar('--theme-primary-50', palette[50])
  setCssVar('--theme-primary-100', palette[100])
  setCssVar('--theme-primary-200', palette[200])
  setCssVar('--theme-primary-300', palette[300])
  setCssVar('--theme-primary-400', palette[400])
  setCssVar('--theme-primary-500', palette[500])
  setCssVar('--theme-primary-600', palette[600])
  setCssVar('--theme-primary-700', palette[700])
  setCssVar('--theme-primary-800', palette[800])
  setCssVar('--theme-primary-900', palette[900])
  setCssVar('--theme-gradient-from', palette.gradientFrom)
  setCssVar('--theme-gradient-via', palette.gradientVia)
  setCssVar('--theme-gradient-to', palette.gradientTo)
  setCssVar('--color-primary', palette[500])
  setCssVar('--color-primary-hover', palette[600])
  setCssVar('--color-primary-light', palette[100])

  // 设置字体CSS变量
  setCssVar('--theme-font-family', fontFamily)

  return settings
}

/**
 * 初始化暗黑/亮色模式
 */
export const initializeThemeMode = (): 'light' | 'dark' => {
  if (typeof window === 'undefined') return 'light'

  const stored = window.localStorage.getItem('theme')
  if (stored === 'dark' || stored === 'light') {
    document.documentElement.classList.toggle('dark', stored === 'dark')
    return stored
  }

  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  document.documentElement.classList.toggle('dark', prefersDark)
  return prefersDark ? 'dark' : 'light'
}
