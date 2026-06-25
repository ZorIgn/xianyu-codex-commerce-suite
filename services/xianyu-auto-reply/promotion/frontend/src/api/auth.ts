/**
 * 推广返佣系统 - 认证API
 *
 * 功能：
 * 1. 用户登录
 * 2. 令牌验证
 * 3. 令牌刷新
 */
import request from '@/utils/request'
import type { LoginResponse } from '@/types'

/**
 * 用户登录
 *
 * 支持极验滑动验证码参数
 */
export async function login(data: {
  username: string
  password: string
  geetest_challenge?: string
  geetest_validate?: string
  geetest_seccode?: string
}): Promise<LoginResponse> {
  const response = await request.post('/api/v1/auth/login', data)
  return response.data
}

/**
 * 验证令牌
 */
export async function verifyToken(): Promise<{
  authenticated: boolean
  user_id?: number
  username?: string
  is_admin?: boolean
  account_limit?: number | null
}> {
  const response = await request.get('/api/v1/auth/verify')
  return response.data
}

/**
 * 刷新令牌
 */
export async function refreshToken(): Promise<LoginResponse> {
  const response = await request.post('/api/v1/auth/refresh')
  return response.data
}
