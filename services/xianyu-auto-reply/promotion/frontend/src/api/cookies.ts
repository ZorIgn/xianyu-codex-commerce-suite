/**
 * 推广返佣系统 - 账号管理API
 *
 * 功能：
 * 1. 查询账号列表（后端分页，支持账号类型筛选）
 * 2. 新增账号（Cookies方式，需指定账号类型）
 * 3. 更新Cookies
 * 4. 启用/禁用账号
 * 5. 更新备注
 */
import request from '@/utils/request'
import type { ApiResponse, PaginatedData, Account, AccountType } from '@/types'

/**
 * 查询账号列表
 */
export async function getAccountList(params: {
  page?: number
  page_size?: number
  keyword?: string
  account_type?: string
}): Promise<ApiResponse<PaginatedData<Account>>> {
  const response = await request.get('/api/v1/cookies/list', { params })
  return response.data
}

/**
 * 新增账号
 *
 * 淘宝类型：传app_key + app_secret
 * 其他类型：传cookies
 */
export async function addAccount(data: {
  account_type: AccountType
  cookies?: string
  app_key?: string
  app_secret?: string
  adzone_id?: string
  remark?: string
}): Promise<ApiResponse<{ id: number; account_id: string }>> {
  const response = await request.post('/api/v1/cookies/add', data)
  return response.data
}

/**
 * 统一修改账号信息
 *
 * 淘宝类型：可修改AppKey/AppSecret/推广位ID/备注
 * 其他类型：可修改Cookies/备注
 */
export async function updateAccount(data: {
  id: number
  app_key?: string
  app_secret?: string
  adzone_id?: string
  cookies?: string
  remark?: string
}): Promise<ApiResponse> {
  const response = await request.put('/api/v1/cookies/update', data)
  return response.data
}

/**
 * 更新Cookies
 */
export async function updateCookies(data: {
  id: number
  cookies: string
}): Promise<ApiResponse> {
  const response = await request.put('/api/v1/cookies/update-cookies', data)
  return response.data
}

/**
 * 启用/禁用账号
 */
export async function toggleAccountStatus(data: {
  id: number
  enabled: boolean
}): Promise<ApiResponse> {
  const response = await request.put('/api/v1/cookies/toggle-status', data)
  return response.data
}

/**
 * 更新备注
 */
export async function updateRemark(data: {
  id: number
  remark: string
}): Promise<ApiResponse> {
  const response = await request.put('/api/v1/cookies/update-remark', data)
  return response.data
}
