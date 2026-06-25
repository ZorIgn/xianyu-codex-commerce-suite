/**
 * 淘宝联盟 - 选品广场API
 *
 * 功能：
 * 1. 选品广场商品搜索
 * 2. 获取可用淘宝账号列表
 */
import request from '@/utils/request'
import type { ApiResponse } from '@/types'

/** 商品信息（升级版API结构） */
export interface Product {
  item_id: string
  title: string
  short_title: string
  pic: string
  white_image: string
  price: string
  zk_final_price: string
  promotion_price: string
  shop_title: string
  brand_name: string
  commission_rate: string
  income_rate: string
  commission_amount: string
  subsidy_rate: string
  subsidy_amount: string
  total_earn: string
  commission_type: string
  volume: string
  tk_total_sales: string
  annual_vol: string
  two_hour_sales: string
  daily_sales: string
  user_type: number
  seller_id: string
  category_name: string
  provcity: string
  real_post_fee: string
  click_url: string
  coupon_share_url: string
  coupon_info: string
  promotion_tags: string[]
  promotion_path: { title: string; desc: string; fee: string }[]
}

/** 排序子选项 */
export interface SortChild {
  label: string
  value: string
}

/** 排序选项 */
export interface SortOption {
  dataKey: string
  title: string
  width?: number
  children?: SortChild[]
}

/** 商品搜索结果 */
export interface ProductSearchResult {
  products: Product[]
  total: number
  sort_options: SortOption[]
}

/** 商品详情信息（详情API返回） */
export interface ProductDetail {
  item_id: string
  title: string
  pic: string
  images: string[]
  price: string
  zk_final_price: string
  volume: string
  shop_title: string
  seller_id: string
  user_type: number
  provcity: string
  cat_name: string
  cat_leaf_name: string
  free_shipment: boolean
  hot_flag: string
  item_url: string
  tk_total_sales: string
  tk_total_commi: string
  coupon_info: string
}

/**
 * 商品详情查询
 *
 * 调用淘宝开放平台 taobao.tbk.item.info.get 接口
 */
export async function getProductDetail(itemId: string): Promise<ApiResponse<ProductDetail>> {
  const response = await request.get('/api/v1/taobao-alliance/product-detail', {
    params: { item_id: itemId },
  })
  return response.data
}

/** 淘口令生成结果 */
export interface TpwdResult {
  tpwd: string
  password_simple: string
}

/**
 * 淘口令生成
 *
 * 调用淘宝开放平台 taobao.tbk.tpwd.create 接口
 * 将推广链接转为淘口令（如 ￥xxx￥）
 */
export async function createTpwd(params: {
  url: string
  text?: string
  logo?: string
}): Promise<ApiResponse<TpwdResult>> {
  const response = await request.get('/api/v1/taobao-alliance/create-tpwd', { params })
  return response.data
}

/**
 * 选品广场商品搜索
 *
 * 调用淘宝开放平台 taobao.tbk.dg.material.optional.upgrade 接口
 */
export async function searchProducts(params: {
  keyword: string
  page?: number
  page_size?: number
  sort?: string
  material_id?: number
  cat?: string
  has_coupon?: boolean
  need_free_shipment?: boolean
  is_tmall?: boolean
  start_tk_rate?: number
  end_tk_rate?: number
  start_price?: number
  end_price?: number
}): Promise<ApiResponse<ProductSearchResult>> {
  const response = await request.get('/api/v1/taobao-alliance/product-search', { params })
  return response.data
}
