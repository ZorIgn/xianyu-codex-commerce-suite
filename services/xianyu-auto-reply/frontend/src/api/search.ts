import { post } from '@/utils/request'

// API前缀
const SEARCH_PREFIX = '/api/v1/items'

// 搜索结果项类型
export interface SearchResultItem {
  item_id: string
  title: string
  price: string
  seller_name?: string
  item_url?: string
  main_image?: string
  publish_time?: string
  tags?: string[]
  area?: string
  want_count?: number
}

// 搜索商品
export const searchItems = async (
  keyword: string, 
  page: number = 1, 
  pageSize: number = 20
): Promise<{ success: boolean; data: SearchResultItem[]; total?: number; error?: string }> => {
  const result = await post<{ 
    success: boolean
    data?: SearchResultItem[]
    total?: number
    error?: string 
  }>(`${SEARCH_PREFIX}/search`, { keyword, page, page_size: pageSize })
  return { 
    success: result.success, 
    data: result.data || [], 
    total: result.total,
    error: result.error
  }
}
