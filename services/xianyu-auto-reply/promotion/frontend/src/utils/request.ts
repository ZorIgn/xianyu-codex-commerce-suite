/**
 * 推广返佣系统 - HTTP请求工具
 *
 * 功能：
 * 1. Axios实例创建与配置
 * 2. 请求拦截器：自动添加Authorization头
 * 3. 响应拦截器：处理401自动刷新令牌
 * 4. 超时时间90秒
 */
import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '@/store/authStore'

const request: AxiosInstance = axios.create({
  baseURL: '',
  timeout: 90000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 是否正在刷新令牌
let isRefreshing = false
// 等待刷新的请求队列
let failedQueue: Array<{
  resolve: (value: unknown) => void
  reject: (reason?: unknown) => void
}> = []

/**
 * 处理等待队列中的请求
 */
const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token)
    }
  })
  failedQueue = []
}

// 请求拦截器
request.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = useAuthStore.getState().token || localStorage.getItem('auth_token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器
request.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    // 401错误且不是刷新令牌请求
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        // 已经在刷新中，将请求加入队列
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        })
          .then((token) => {
            if (originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${token}`
            }
            return request(originalRequest)
          })
          .catch((err) => Promise.reject(err))
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        const refreshToken = localStorage.getItem('refresh_token')
        if (!refreshToken) {
          throw new Error('No refresh token')
        }

        const response = await axios.post('/api/v1/auth/refresh', null, {
          headers: { Authorization: `Bearer ${refreshToken}` },
        })

        if (response.data?.success && response.data?.token) {
          const { token, refresh_token } = response.data
          const authStore = useAuthStore.getState()
          authStore.updateTokens(token, refresh_token)

          processQueue(null, token)

          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${token}`
          }
          return request(originalRequest)
        } else {
          throw new Error('Refresh failed')
        }
      } catch (refreshError) {
        processQueue(refreshError, null)
        useAuthStore.getState().clearAuth()
        window.location.href = '/login'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)

/**
 * 从API响应中提取错误消息
 */
export function getApiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data
    if (data?.message) return data.message
    if (data?.msg) return data.msg
    if (data?.detail) {
      if (typeof data.detail === 'string') return data.detail
      if (Array.isArray(data.detail)) return data.detail.map((d: { msg: string }) => d.msg).join(', ')
    }
  }
  if (error instanceof Error) return error.message
  return '请求失败'
}

export default request
