/**
 * 版本检测 API
 *
 * 功能：
 * 1. 获取系统当前版本号
 * 2. 向后端请求检查更新（后端再向远程更新服务器代理请求）
 */
import { get } from '@/utils/request'
import type { ApiResponse } from '@/types'

const PREFIX = '/api/v1/version'

/** 当前版本信息 */
export interface CurrentVersion {
  version: string
}

/** 更新检查结果 */
export interface VersionCheckResult {
  /** 是否有新版本 */
  has_update: boolean
  /** 当前版本号 */
  current_version: string
  /** 远程版本号 */
  remote_version: string
  /** 更新说明（可能包含 \n） */
  description: string
  /** 远程下载文件名 */
  filename: string
  /** 完整下载地址 */
  download_url: string
}

/** 获取当前版本号 */
export const getCurrentVersion = async (): Promise<
  ApiResponse & { data?: CurrentVersion }
> => {
  return get(`${PREFIX}/current`)
}

/** 检查是否有新版本 */
export const checkUpdate = async (): Promise<
  ApiResponse & { data?: VersionCheckResult }
> => {
  return get(`${PREFIX}/check`)
}
