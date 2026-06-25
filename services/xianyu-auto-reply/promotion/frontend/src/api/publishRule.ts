/**
 * 返佣系统 - 发布规则API
 *
 * 功能：
 * 1. 发布规则列表查询
 * 2. 新建/更新/删除发布规则
 * 3. 启用/禁用规则
 * 4. 手动执行规则
 * 5. 查询闲鱼账号列表
 */
import request from '@/utils/request'
import type { ApiResponse } from '@/types'

/** 发布规则 */
export interface PublishRule {
  id: number
  owner_id: number
  rule_name: string
  account_id: string
  daily_count: number
  total_published_count: number
  enabled: boolean
  remark: string
  last_run_date: string
  today_count: number
  last_run_at: string
  created_at: string
  updated_at: string
}

/** 规则列表响应 */
export interface PublishRuleListResult {
  list: PublishRule[]
  total: number
}

/** 新建规则参数 */
export interface PublishRuleCreateParams {
  rule_name: string
  account_id: string
  daily_count?: number
  enabled?: boolean
  remark?: string
}

/** 更新规则参数 */
export interface PublishRuleUpdateParams {
  rule_name?: string
  account_id?: string
  daily_count?: number
  enabled?: boolean
  remark?: string
}

/** 闲鱼账号选项 */
export interface XYAccountOption {
  account_id: string
  display_name: string
}

export interface PublishRuleExecuteTask {
  task_id: string
  rule_id: number
  status: string
  message: string
  published_count: number
  created_at: string
  started_at: string
  finished_at: string
  updated_at: string
}

/** 查询发布规则列表 */
export async function listPublishRules(params: {
  page?: number
  page_size?: number
}): Promise<ApiResponse<PublishRuleListResult>> {
  const response = await request.get('/api/v1/publish-rule/list', { params })
  return response.data
}

/** 新建发布规则 */
export async function createPublishRule(data: PublishRuleCreateParams): Promise<ApiResponse<PublishRule>> {
  const response = await request.post('/api/v1/publish-rule/create', data)
  return response.data
}

/** 更新发布规则 */
export async function updatePublishRule(ruleId: number, data: PublishRuleUpdateParams): Promise<ApiResponse<PublishRule>> {
  const response = await request.put(`/api/v1/publish-rule/update/${ruleId}`, data)
  return response.data
}

/** 删除发布规则 */
export async function deletePublishRule(ruleId: number): Promise<ApiResponse<null>> {
  const response = await request.delete(`/api/v1/publish-rule/delete/${ruleId}`)
  return response.data
}

/** 启用/禁用发布规则 */
export async function togglePublishRule(ruleId: number, enabled: boolean): Promise<ApiResponse<null>> {
  const response = await request.post(`/api/v1/publish-rule/toggle/${ruleId}`, { enabled })
  return response.data
}

/** 手动执行发布规则 */
export async function executePublishRule(ruleId: number): Promise<ApiResponse<PublishRuleExecuteTask>> {
  const response = await request.post(`/api/v1/publish-rule/execute/${ruleId}`)
  return response.data
}

/** 查询发布规则执行状态 */
export async function getExecutePublishRuleStatus(taskId: string): Promise<ApiResponse<PublishRuleExecuteTask>> {
  const response = await request.get(`/api/v1/publish-rule/execute-status/${taskId}`)
  return response.data
}

/** 查询闲鱼账号列表（供下拉选择） */
export async function listXYAccounts(): Promise<ApiResponse<XYAccountOption[]>> {
  const response = await request.get('/api/v1/publish-rule/xy-accounts')
  return response.data
}
