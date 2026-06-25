/**
 * 激活码公开API接口
 *
 * 功能：
 * 1. 根据机器码生成试用激活码（15天）
 * 2. 根据机器码生成续期码（5天）
 * 均为公开接口，无需登录
 */
import { post } from '@/utils/request'

const ACTIVATION_PREFIX = '/api/v1/activation'

/** 激活码生成响应数据 */
export interface ActivationResult {
  activation_code: string
  expire_time: string
  days: number
  machine_id: string
}

/** 续期码生成响应数据 */
export interface RenewResult {
  renew_code: string
  days: number
  machine_id: string
}

/** 通用API响应 */
interface ApiResp<T> {
  success: boolean
  message: string | null
  data: T | null
}

/** 生成试用激活码（公开接口，无需登录） */
export const generateTrialActivation = (machineId: string): Promise<ApiResp<ActivationResult>> => {
  return post(`${ACTIVATION_PREFIX}/generate`, { machine_id: machineId })
}

/** 生成续期码（公开接口，无需登录） */
export const generateRenewCode = (machineId: string): Promise<ApiResp<RenewResult>> => {
  return post(`${ACTIVATION_PREFIX}/renew`, { machine_id: machineId })
}

/** 历史记录项 */
export interface ActivationHistoryRecord {
  id: number
  code_type: string
  code_type_name: string
  generated_code: string
  days: number
  ip_address: string
  expire_time: string | null
  expired: boolean | null
  expire_status: string
  created_at: string
}

/** 历史记录查询响应 */
export interface ActivationHistoryResult {
  records: ActivationHistoryRecord[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

/** 查询激活码生成历史（公开接口，无需登录） */
export const getActivationHistory = (
  machineId: string,
  page: number = 1,
  pageSize: number = 20
): Promise<ApiResp<ActivationHistoryResult>> => {
  return post(`${ACTIVATION_PREFIX}/history?page=${page}&page_size=${pageSize}`, { machine_id: machineId })
}
