import { post } from '@/utils/request'

const COMPASS_PREFIX = '/api/v1/compass/goofish'

export interface GoofishCompassItem {
  item_id: string
  title: string
  price: string
  area?: string
  seller_name?: string
  item_url?: string
  main_image?: string
  publish_time?: string
  want_count?: number
  view_count?: number
  description?: string
  detail_error?: string
}

export interface GoofishCompassSearchResponse {
  success: boolean
  items: GoofishCompassItem[]
  total: number
  total_available?: number
  error?: string
}

export interface GoofishCompassSearchRequest {
  cookie_id: string
  keyword: string
  start_page?: number
  pages?: number
  page_size?: number
  fetch_detail?: boolean
  detail_limit?: number
}

export const goofishCompassSearch = async (
  payload: GoofishCompassSearchRequest,
): Promise<GoofishCompassSearchResponse> => {
  return post<GoofishCompassSearchResponse>(`${COMPASS_PREFIX}/search`, payload, { timeout: 300000 })
}

