/**
 * COOKIES刷新批次详情页面
 *
 * 功能：
 * 1. 显示批次汇总信息（账号数 / 初始化 / 成功 / 失败）
 * 2. 显示该批次所有账号的 COOKIES 刷新日志列表
 * 3. 支持按状态筛选 + 客户端分页
 */
import { CheckCircle, Clock, Users, XCircle } from 'lucide-react'
import {
  getCookiesRefreshBatchDetail,
  type CookiesRefreshBatchDetail,
  type CookiesRefreshLog,
} from '@/api/cookiesRefreshLogs'
import {
  BatchLogDetail,
  renderAccountIdCell,
  renderDateTimeText,
  renderDescriptionCell,
  renderStatusBadge,
  type BatchLogStatusInfo,
  type BatchLogSummaryCard,
  type BatchLogTableColumn,
} from '@/components/common/BatchLogDetail'

const summaryCards: BatchLogSummaryCard<CookiesRefreshBatchDetail>[] = [
  {
    icon: Users,
    iconBgClass: 'bg-purple-100 dark:bg-purple-900/30',
    iconColorClass: 'text-purple-600 dark:text-purple-400',
    label: '处理账号数',
    value: (batch) => batch.total_accounts,
  },
  {
    icon: Clock,
    iconBgClass: 'bg-amber-100 dark:bg-amber-900/30',
    iconColorClass: 'text-amber-600 dark:text-amber-400',
    label: '初始化',
    value: (batch) => batch.initialized_count,
    valueClass: 'text-2xl font-bold text-amber-600 dark:text-amber-400',
  },
  {
    icon: CheckCircle,
    iconBgClass: 'bg-green-100 dark:bg-green-900/30',
    iconColorClass: 'text-green-600 dark:text-green-400',
    label: '成功',
    value: (batch) => batch.success_count,
    valueClass: 'text-2xl font-bold text-green-600 dark:text-green-400',
  },
  {
    icon: XCircle,
    iconBgClass: 'bg-red-100 dark:bg-red-900/30',
    iconColorClass: 'text-red-600 dark:text-red-400',
    label: '失败',
    value: (batch) => batch.failed_count,
    valueClass: 'text-2xl font-bold text-red-600 dark:text-red-400',
  },
]

const STATUS_INFO_MAP: Record<string, BatchLogStatusInfo> = {
  initialized: {
    label: '初始化',
    color: 'text-amber-600 dark:text-amber-400',
    Icon: Clock,
  },
  success: {
    label: '成功',
    color: 'text-green-600 dark:text-green-400',
    Icon: CheckCircle,
  },
  failed: {
    label: '失败',
    color: 'text-red-600 dark:text-red-400',
    Icon: XCircle,
  },
}

const columns: BatchLogTableColumn<CookiesRefreshLog>[] = [
  { title: '账号ID', render: (log) => renderAccountIdCell(log.account_id) },
  {
    title: '状态',
    render: (log) =>
      renderStatusBadge(
        STATUS_INFO_MAP[log.status] ?? {
          label: log.status,
          color: 'text-slate-500 dark:text-slate-400',
          Icon: Clock,
        },
      ),
  },
  { title: '更新字段数', render: (log) => log.updated_cookie_count },
  { title: '说明', render: (log) => renderDescriptionCell(log.error_message, 60) },
  {
    title: '下次到期时间',
    render: (log) => renderDateTimeText(log.next_expire_at),
  },
  { title: '执行时间', render: (log) => renderDateTimeText(log.created_at) },
]

export function CookiesRefreshBatchDetailPage() {
  return (
    <BatchLogDetail<CookiesRefreshBatchDetail, CookiesRefreshLog>
      fetchDetail={getCookiesRefreshBatchDetail}
      backPath="/admin/cookies-refresh-batches"
      pageTitle="COOKIES刷新批次详情"
      summaryCards={summaryCards}
      summaryGridClass="grid-cols-2 md:grid-cols-4"
      logTitle="刷新日志"
      statusOptions={[
        { value: 'all', label: '全部状态' },
        { value: 'initialized', label: '初始化' },
        { value: 'success', label: '成功' },
        { value: 'failed', label: '失败' },
      ]}
      columns={columns}
      cardHeightStyle={{ height: 'calc(100vh - 380px)', minHeight: '320px' }}
      enableClientPagination
      defaultPageSize={20}
      loadErrorMessage="加载批次详情失败"
    />
  )
}
