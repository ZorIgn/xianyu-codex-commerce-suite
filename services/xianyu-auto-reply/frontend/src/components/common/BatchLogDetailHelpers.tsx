/**
 * 批次日志详情页常用单元格 / 徽章渲染函数。
 *
 * 说明：
 * 1. 所有 renderXxx 都返回 ReactNode，配合 BatchLogDetail 的 columns/summaryCards 配置使用
 * 2. 单独拆文件是为了控制 BatchLogDetail.tsx 的单文件行数（项目约束 500 行以内）
 * 3. 调用方仍可从 ``@/components/common/BatchLogDetail`` 统一 import，这里的符号会被主模块 re-export
 */
import { CheckCircle, XCircle, type LucideIcon } from 'lucide-react'
import { formatDateTime } from '@/utils/date'

/**
 * 状态徽章信息：用于自定义状态展示（图标 + 文字 + 颜色）。
 */
export interface BatchLogStatusInfo {
  label: string
  color: string
  Icon: LucideIcon
}

/**
 * 渲染状态徽章（图标 + 文字 + 颜色）。
 */
export function renderStatusBadge(info: BatchLogStatusInfo) {
  const Icon = info.Icon
  return (
    <span className={`inline-flex items-center gap-1 ${info.color}`}>
      <Icon className="w-3.5 h-3.5" />
      {info.label}
    </span>
  )
}

/**
 * 渲染最常见的成功 / 失败二态徽章。
 */
export function renderSuccessFailedBadge(status: string) {
  if (status === 'success') {
    return renderStatusBadge({
      label: '成功',
      color: 'text-green-600 dark:text-green-400',
      Icon: CheckCircle,
    })
  }
  return renderStatusBadge({
    label: '失败',
    color: 'text-red-600 dark:text-red-400',
    Icon: XCircle,
  })
}

/**
 * 渲染截断展示的错误信息（默认超过 50 字符截断，鼠标悬停显示完整）。
 */
export function renderTruncatedError(
  message: string | null | undefined,
  maxLength = 50,
) {
  if (!message) {
    return <span className="text-slate-300 dark:text-slate-600">-</span>
  }
  const text = message.length > maxLength ? `${message.substring(0, maxLength)}...` : message
  return (
    <span className="text-red-500 dark:text-red-400 text-sm" title={message}>
      {text}
    </span>
  )
}

/**
 * 渲染完整错误信息（不截断，用于卡片宽度足够的场景，如消息通知关闭）。
 */
export function renderFullError(message: string | null | undefined) {
  if (!message) {
    return <span className="text-slate-400">-</span>
  }
  return <span className="text-red-500 dark:text-red-400 text-sm break-all">{message}</span>
}

/**
 * 渲染普通灰字时间。
 */
export function renderDateTimeText(value: string | null | undefined) {
  return (
    <span className="text-sm text-slate-500 dark:text-slate-400">{formatDateTime(value)}</span>
  )
}

/**
 * 渲染常见的“账号 ID”单元格（蓝色加粗）。
 */
export function renderAccountIdCell(accountId: string) {
  return <span className="font-medium text-blue-600 dark:text-blue-400">{accountId}</span>
}

/**
 * 渲染等宽字体单元格（订单号、商品 ID 等）。
 */
export function renderMonoCell(value: string) {
  return <span className="font-mono text-sm">{value}</span>
}

/**
 * 渲染普通描述/说明列（用于 ``说明`` 列）。
 */
export function renderDescriptionCell(message: string | null | undefined, maxLength = 60) {
  if (!message) {
    return <span className="text-slate-300 dark:text-slate-600">-</span>
  }
  const text = message.length > maxLength ? `${message.substring(0, maxLength)}...` : message
  return (
    <span className="text-slate-600 dark:text-slate-400 text-sm" title={message}>
      {text}
    </span>
  )
}
