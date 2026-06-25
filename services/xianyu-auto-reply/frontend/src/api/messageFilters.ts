/**
 * 消息过滤规则 API
 * 
 * 功能：
 * - 获取消息过滤规则列表
 * - 创建消息过滤规则
 * - 更新消息过滤规则
 * - 删除消息过滤规则
 * - 切换启用状态
 */
import { get, post, put, del } from '@/utils/request'
import type { MessageFilter, MessageFilterBatchCreate, MessageFilterCreate, MessageFilterUpdate } from '@/types'

const PREFIX = '/api/v1/message-filters'

/**
 * 获取消息过滤规则列表
 * @param accountId 可选，按账号筛选
 */
export async function getMessageFilters(accountId?: string): Promise<MessageFilter[]> {
  const params = accountId ? { account_id: accountId } : {}
  const result = await get<{ success: boolean; data: MessageFilter[] }>(PREFIX, { params })
  return result?.data || []
}

/**
 * 创建消息过滤规则
 * @param data 创建数据，支持多选filter_types
 */
export async function createMessageFilter(data: MessageFilterCreate): Promise<{ success: boolean; message: string; data?: { created_ids: number[] } }> {
  return post(PREFIX, data)
}

export async function createMessageFiltersBatch(
  data: MessageFilterBatchCreate,
): Promise<{ success: boolean; message: string; data?: { created_ids: number[]; created_count: number; failed_count: number } }> {
  return post(`${PREFIX}/batch-create`, data)
}

/**
 * 更新消息过滤规则
 * @param id 规则ID
 * @param data 更新数据
 */
export async function updateMessageFilter(id: number, data: MessageFilterUpdate): Promise<{ success: boolean; message: string }> {
  return put(`${PREFIX}/${id}`, data)
}

/**
 * 删除消息过滤规则
 * @param id 规则ID
 */
export async function deleteMessageFilter(id: number): Promise<{ success: boolean; message: string }> {
  return del(`${PREFIX}/${id}`)
}

/**
 * 批量删除消息过滤规则
 * @param ids 规则ID数组
 */
export async function batchDeleteMessageFilters(ids: number[]): Promise<{ success: boolean; message: string; data?: { deleted_count: number } }> {
  return post(`${PREFIX}/batch-delete`, { ids })
}

/**
 * 切换消息过滤规则启用状态
 * @param id 规则ID
 */
export async function toggleMessageFilter(id: number): Promise<{ success: boolean; message: string; data?: { enabled: boolean } }> {
  return put(`${PREFIX}/${id}/toggle`, {})
}
