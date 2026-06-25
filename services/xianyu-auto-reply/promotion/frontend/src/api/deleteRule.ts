/**
 * 返佣系统 - 删除规则API
 *
 * 功能：
 * 1. 删除规则列表查询
 * 2. 新建/更新/删除规则
 * 3. 启用/禁用规则
 * 4. 查询闲鱼账号列表
 */
import request from '@/utils/request'
import type { ApiResponse } from '@/types'

/** 删除规则 */
export interface DeleteRule {
  id: number
  owner_id: number
  rule_name: string
  account_id: string
  daily_count: number
  min_publish_days: number
  total_deleted_count: number
  enabled: boolean
  remark: string
  last_run_date: string
  today_count: number
  last_run_at: string
  created_at: string
  updated_at: string
}

/** 规则列表响应 */
export interface DeleteRuleListResult {
  list: DeleteRule[]
  total: number
}

/** 新建规则参数 */
export interface DeleteRuleCreateParams {
  rule_name: string
  account_id: string
  daily_count?: number
  min_publish_days?: number
  enabled?: boolean
  remark?: string
}

/** 更新规则参数 */
export interface DeleteRuleUpdateParams {
  rule_name?: string
  account_id?: string
  daily_count?: number
  min_publish_days?: number
  enabled?: boolean
  remark?: string
}

/** 闲鱼账号选项 */
export interface XYAccountOption {
  account_id: string
  display_name: string
}

/** 查询删除规则列表 */
export async function listDeleteRules(params: {
  page?: number
  page_size?: number
}): Promise<ApiResponse<DeleteRuleListResult>> {
  const response = await request.get('/api/v1/delete-rule/list', { params })
  return response.data
}

/** 新建删除规则 */
export async function createDeleteRule(data: DeleteRuleCreateParams): Promise<ApiResponse<DeleteRule>> {
  const response = await request.post('/api/v1/delete-rule/create', data)
  return response.data
}

/** 更新删除规则 */
export async function updateDeleteRule(ruleId: number, data: DeleteRuleUpdateParams): Promise<ApiResponse<DeleteRule>> {
  const response = await request.put(`/api/v1/delete-rule/update/${ruleId}`, data)
  return response.data
}

/** 删除删除规则 */
export async function deleteDeleteRule(ruleId: number): Promise<ApiResponse<null>> {
  const response = await request.delete(`/api/v1/delete-rule/delete/${ruleId}`)
  return response.data
}

/** 启用/禁用删除规则 */
export async function toggleDeleteRule(ruleId: number, enabled: boolean): Promise<ApiResponse<null>> {
  const response = await request.post(`/api/v1/delete-rule/toggle/${ruleId}`, { enabled })
  return response.data
}

/** 查询闲鱼账号列表（供下拉选择） */
export async function listDeleteRuleXYAccounts(): Promise<ApiResponse<XYAccountOption[]>> {
  const response = await request.get('/api/v1/delete-rule/xy-accounts')
  return response.data
}
