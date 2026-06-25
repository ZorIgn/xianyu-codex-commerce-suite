/**
 * 意见反馈API
 * 
 * 功能：
 * 1. 获取反馈列表
 * 2. 获取反馈详情（含对话消息）
 * 3. 提交反馈
 * 4. 回复反馈（用户和管理员都可以）
 * 5. 标记解决/未解决
 * 6. 删除反馈
 */
import { get, post, put, del } from '@/utils/request'
import type { ApiResponse } from '@/types'

const PREFIX = '/api/v1/feedbacks'

export interface FeedbackStats {
  total: number
  resolved: number
  pending: number
}

export interface FeedbackMessage {
  id: number
  is_admin: boolean
  content: string
  created_at: string | null
}

export interface Feedback {
  id: number
  user_id: number
  cookie_id: string | null
  title: string
  content: string
  feedback_type: 'FEATURE' | 'BUG' | 'OTHER'
  images: string[]
  is_resolved: boolean
  resolved_at: string | null
  admin_reply: string | null
  message_count?: number
  created_at: string
}

export interface FeedbackDetail extends Omit<Feedback, 'admin_reply'> {
  messages: FeedbackMessage[]
}

export interface FeedbackListResponse {
  items: Feedback[]
  total: number
  page: number
  page_size: number
}

// 获取反馈统计
export const getFeedbackStats = async (): Promise<ApiResponse & { data?: FeedbackStats }> => {
  return get(`${PREFIX}/stats`)
}

// 获取反馈列表
export const getFeedbacks = async (params?: {
  page?: number
  page_size?: number
  is_resolved?: boolean
  feedback_type?: string
}): Promise<ApiResponse & { data?: FeedbackListResponse }> => {
  const query = new URLSearchParams()
  if (params?.page) query.append('page', String(params.page))
  if (params?.page_size) query.append('page_size', String(params.page_size))
  if (params?.is_resolved !== undefined) query.append('is_resolved', String(params.is_resolved))
  if (params?.feedback_type) query.append('feedback_type', params.feedback_type)
  return get(`${PREFIX}?${query.toString()}`)
}

// 获取反馈详情（含对话消息）
export const getFeedbackDetail = async (id: number): Promise<ApiResponse & { data?: FeedbackDetail }> => {
  return get(`${PREFIX}/${id}`)
}

// 提交反馈
export const createFeedback = async (data: {
  title: string
  content: string
  feedback_type: string
  cookie_id?: string
  images?: string[]
}): Promise<ApiResponse> => {
  const query = new URLSearchParams()
  query.append('title', data.title)
  query.append('content', data.content)
  query.append('feedback_type', data.feedback_type)
  if (data.cookie_id) query.append('cookie_id', data.cookie_id)
  if (data.images && data.images.length > 0) {
    query.append('images', JSON.stringify(data.images))
  }
  return post(`${PREFIX}?${query.toString()}`)
}

// 回复反馈（用户和管理员都可以）
export const replyFeedback = async (id: number, content: string): Promise<ApiResponse> => {
  const query = new URLSearchParams()
  query.append('content', content)
  return post(`${PREFIX}/${id}/reply?${query.toString()}`)
}

// 标记为已解决（管理员）
export const resolveFeedback = async (id: number): Promise<ApiResponse> => {
  return put(`${PREFIX}/${id}/resolve`)
}

// 标记为未解决（管理员）
export const unresolveFeedback = async (id: number): Promise<ApiResponse> => {
  return put(`${PREFIX}/${id}/unresolve`)
}

// 删除反馈
export const deleteFeedback = async (id: number): Promise<ApiResponse> => {
  return del(`${PREFIX}/${id}`)
}
