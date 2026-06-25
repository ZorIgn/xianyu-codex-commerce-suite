/**
 * 推广返佣系统 - 类型定义
 */

/* ==================== 用户相关 ==================== */
export interface User {
  user_id: number
  username: string
  is_admin: boolean
  account_limit?: number | null
}

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  success: boolean
  message?: string
  token?: string
  refresh_token?: string
  user_id?: number
  username?: string
  is_admin?: boolean
  account_limit?: number | null
}

/* ==================== 账号相关 ==================== */
/** 账号类型枚举 */
export type AccountType = 'TAOBAO' | 'JD' | 'MEITUAN'

/** 账号类型中文映射 */
export const ACCOUNT_TYPE_OPTIONS: { value: AccountType; label: string }[] = [
  { value: 'TAOBAO', label: '淘宝' },
  { value: 'JD', label: '京东' },
  { value: 'MEITUAN', label: '美团' },
]

export interface Account {
  id: number
  account_id: string
  account_type: AccountType
  account_type_label: string
  display_name?: string
  owner_id?: number
  enabled: boolean
  remark?: string
  app_key?: string
  app_secret_masked?: string
  adzone_id?: string
  created_at?: string
  updated_at?: string
}

/* ==================== 仪表盘统计 ==================== */
export interface DashboardStats {
  total_accounts: number
  active_accounts: number
  inactive_accounts: number
  total_users?: number
}

/* ==================== API通用响应 ==================== */
export interface ApiResponse<T = unknown> {
  success: boolean
  message?: string
  data?: T
}

export interface PaginatedData<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}
