/**
 * 返佣系统 - 素材库API
 *
 * 功能：
 * 1. 素材列表查询（分页 + 关键词搜索）
 * 2. 更新素材
 * 3. 删除素材
 */
import request from '@/utils/request'
import type { ApiResponse } from '@/types'

/** 素材项 */
export interface Material {
  id: number
  owner_id: number
  account_id: string
  rule_id: number
  item_id: string
  title: string
  price: number
  stock: number
  description: string
  images: string[]
  click_url: string
  coupon_url: string
  coupon_info: string
  tpwd: string
  short_url: string
  original_price: string
  promotion_price: string
  commission_rate: string
  commission_amount: string
  shop_title: string
  volume: string
  publish_status: 'unpublished' | 'published' | 'failed'
  published: boolean
  published_at: string
  published_item_id: string
  publish_random_str: string
  created_at: string
  updated_at: string
}

/** 素材列表响应 */
export interface MaterialListResult {
  list: Material[]
  total: number
}

/** 更新素材参数 */
export interface MaterialUpdateParams {
  title?: string
  price?: number
  description?: string
  images?: string
  click_url?: string
  coupon_url?: string
  coupon_info?: string
  tpwd?: string
  short_url?: string
}

/** 查询素材列表 */
export async function listMaterials(params: {
  page?: number
  page_size?: number
  keyword?: string
  account_id?: string
  publish_status?: 'unpublished' | 'published' | 'failed'
}): Promise<ApiResponse<MaterialListResult>> {
  const response = await request.get('/api/v1/material/list', { params })
  return response.data
}

/** 更新素材 */
export async function updateMaterial(id: number, data: MaterialUpdateParams): Promise<ApiResponse<Material>> {
  const response = await request.put(`/api/v1/material/update/${id}`, data)
  return response.data
}

/** 删除素材 */
export async function deleteMaterial(id: number): Promise<ApiResponse<null>> {
  const response = await request.delete(`/api/v1/material/delete/${id}`)
  return response.data
}

/** 批量删除素材 */
export async function batchDeleteMaterials(ids: number[]): Promise<ApiResponse<null>> {
  const response = await request.post('/api/v1/material/batch-delete', { ids })
  return response.data
}
