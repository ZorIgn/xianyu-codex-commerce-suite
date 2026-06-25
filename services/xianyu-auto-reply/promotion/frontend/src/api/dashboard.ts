/**
 * 推广返佣系统 - 仪表盘API
 *
 * 获取仪表盘统计数据
 */
import request from '@/utils/request'
import type { ApiResponse, DashboardStats } from '@/types'

/**
 * 获取仪表盘统计
 */
export async function getDashboardStats(): Promise<ApiResponse<DashboardStats>> {
  const response = await request.get('/api/v1/dashboard/stats')
  return response.data
}
