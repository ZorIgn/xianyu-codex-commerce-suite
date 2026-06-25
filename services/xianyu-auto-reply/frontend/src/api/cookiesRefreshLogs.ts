/**
 * COOKIES刷新日志API
 *
 * 功能：
 * 1. 获取COOKIES刷新批次列表
 * 2. 获取COOKIES刷新批次详情
 */
import {
  createBatchLogApi,
  type BatchDetailResponse,
  type BatchListResponse,
} from './batchLogFactory'

export interface CookiesRefreshLog {
  id: number
  batch_id: string
  account_id: string
  status: 'initialized' | 'success' | 'failed'
  updated_cookie_count: number
  next_expire_at: string | null
  error_message: string | null
  created_at: string
}

export interface CookiesRefreshBatch {
  batch_id: string
  executed_at: string
  total_accounts: number
  initialized_count: number
  success_count: number
  failed_count: number
}

export interface CookiesRefreshBatchDetail extends CookiesRefreshBatch {
  logs: CookiesRefreshLog[]
}

export type CookiesRefreshBatchListResponse = BatchListResponse<CookiesRefreshBatch>
export type CookiesRefreshBatchDetailResponse = BatchDetailResponse<CookiesRefreshBatchDetail | null>

const api = createBatchLogApi<CookiesRefreshBatch, CookiesRefreshBatchDetail | null>({
  batches: 'cookies-refresh-batches',
})

export const getCookiesRefreshBatches = api.getBatches
export const getCookiesRefreshBatchDetail = api.getBatchDetail
