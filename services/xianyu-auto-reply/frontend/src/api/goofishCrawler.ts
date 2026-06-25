import { del, get, post } from '@/utils/request'

const PREFIX = '/api/v1/goofish/crawler'

export interface GoofishCrawlJob {
  id: number
  cookie_id: string
  keyword: string
  interval_seconds: number
  start_page: number
  pages: number
  page_size: number
  fetch_detail: boolean
  detail_limit: number
  enabled: boolean
  running: boolean
  last_run_at?: string
  last_error?: string
  item_count?: number
  latest_item_fetched_at?: string
}

export interface GoofishCrawlItem {
  job_id: number
  item_id: string
  title?: string
  price?: string
  area?: string
  seller_name?: string
  item_url?: string
  main_image?: string
  publish_time?: string
  want_count?: number
  view_count?: number
  description?: string
  detail_error?: string
  fetched_at?: string
}

export interface CreateGoofishCrawlJobRequest {
  cookie_id: string
  keyword: string
  interval_seconds?: number
  start_page?: number
  pages?: number
  page_size?: number
  fetch_detail?: boolean
  detail_limit?: number
  enabled?: boolean
}

export const listGoofishCrawlJobs = async (): Promise<{ jobs: GoofishCrawlJob[] }> => {
  return get(`${PREFIX}/jobs`)
}

export const createGoofishCrawlJob = async (
  payload: CreateGoofishCrawlJobRequest,
): Promise<{ success: boolean; job_id?: number; message?: string }> => {
  return post(`${PREFIX}/jobs`, payload)
}

export const startGoofishCrawlJob = async (jobId: number): Promise<{ success: boolean }> => {
  return post(`${PREFIX}/jobs/${jobId}/start`)
}

export const stopGoofishCrawlJob = async (jobId: number): Promise<{ success: boolean }> => {
  return post(`${PREFIX}/jobs/${jobId}/stop`)
}

export const runOnceGoofishCrawlJob = async (
  jobId: number,
): Promise<{ success: boolean; upserted: number; total: number; error?: string }> => {
  return post(`${PREFIX}/jobs/${jobId}/run-once`)
}

export const listGoofishCrawlItems = async (
  jobId: number,
  params?: { limit?: number; offset?: number },
): Promise<{ items: GoofishCrawlItem[] }> => {
  const q = new URLSearchParams()
  if (params?.limit !== undefined) q.set('limit', String(params.limit))
  if (params?.offset !== undefined) q.set('offset', String(params.offset))
  const suffix = q.toString() ? `?${q.toString()}` : ''
  return get(`${PREFIX}/jobs/${jobId}/items${suffix}`)
}

export const deleteGoofishCrawlJob = async (jobId: number): Promise<{ success: boolean }> => {
  return del(`${PREFIX}/jobs/${jobId}`)
}
