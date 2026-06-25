/**
 * 返佣系统 - 选品规则API
 *
 * 功能：
 * 1. 选品规则列表查询
 * 2. 新建/更新/删除选品规则
 * 3. 启用/禁用规则
 */
import request from '@/utils/request'
import type { ApiResponse } from '@/types'

/** 选品规则 */
export interface ProductRule {
  id: number
  owner_id: number
  account_id: string
  rule_name: string
  cat: string
  cat_name: string
  keyword: string
  sort: string
  daily_count: number
  total_selected_count: number
  enabled: boolean
  remark: string
  last_run_date: string
  today_count: number
  last_run_at: string
  created_at: string
  updated_at: string
}

/** 规则列表响应 */
export interface ProductRuleListResult {
  list: ProductRule[]
  total: number
}

/** 新建规则参数 */
export interface RuleCreateParams {
  rule_name: string
  account_id: string
  cat?: string
  cat_name?: string
  keyword?: string
  sort?: string
  daily_count?: number
  enabled?: boolean
  remark?: string
}

/** 更新规则参数 */
export interface RuleUpdateParams {
  rule_name?: string
  account_id?: string
  cat?: string
  cat_name?: string
  keyword?: string
  sort?: string
  daily_count?: number
  enabled?: boolean
  remark?: string
}

/** 查询选品规则列表 */
export async function listProductRules(params: {
  page?: number
  page_size?: number
}): Promise<ApiResponse<ProductRuleListResult>> {
  const response = await request.get('/api/v1/product-rule/list', { params })
  return response.data
}

/** 新建选品规则 */
export async function createProductRule(data: RuleCreateParams): Promise<ApiResponse<ProductRule>> {
  const response = await request.post('/api/v1/product-rule/create', data)
  return response.data
}

/** 更新选品规则 */
export async function updateProductRule(ruleId: number, data: RuleUpdateParams): Promise<ApiResponse<ProductRule>> {
  const response = await request.put(`/api/v1/product-rule/update/${ruleId}`, data)
  return response.data
}

/** 删除选品规则 */
export async function deleteProductRule(ruleId: number): Promise<ApiResponse<null>> {
  const response = await request.delete(`/api/v1/product-rule/delete/${ruleId}`)
  return response.data
}

/** 启用/禁用选品规则 */
export async function toggleProductRule(ruleId: number, enabled: boolean): Promise<ApiResponse<null>> {
  const response = await request.post(`/api/v1/product-rule/toggle/${ruleId}`, { enabled })
  return response.data
}

/** 手动执行选品规则（不受当日限制） */
export async function executeProductRule(ruleId: number): Promise<ApiResponse<null>> {
  const response = await request.post(`/api/v1/product-rule/execute/${ruleId}`)
  return response.data
}
