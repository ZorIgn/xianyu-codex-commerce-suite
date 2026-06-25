/**
 * 登录续期批次详情页面
 *
 * 功能：
 * 1. 显示批次汇总信息（含令牌刷新、Session 过期、健康率等扩展指标）
 * 2. 显示该批次所有账号续期日志列表
 * 3. 支持按状态筛选（含 token_refreshed / session_expired 等多状态）
 */
import {
  AlertTriangle,
  CheckCircle,
  Clock,
  Key,
  Users,
  XCircle,
} from 'lucide-react'
import {
  getLoginRenewBatchDetail,
  type LoginRenewBatchDetail,
  type LoginRenewLog,
} from '@/api/loginRenewLogs'
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

const summaryCards: BatchLogSummaryCard<LoginRenewBatchDetail>[] = [
  {
    icon: Users,
    iconBgClass: 'bg-purple-100 dark:bg-purple-900/30',
    iconColorClass: 'text-purple-600 dark:text-purple-400',
    label: '处理账号数',
    value: (batch) => batch.total_accounts,
  },
  {
    icon: CheckCircle,
    iconBgClass: 'bg-green-100 dark:bg-green-900/30',
    iconColorClass: 'text-green-600 dark:text-green-400',
    label: '正常',
    value: (batch) => batch.success_count,
    valueClass: 'text-2xl font-bold text-green-600 dark:text-green-400',
  },
  {
    icon: Key,
    iconBgClass: 'bg-blue-100 dark:bg-blue-900/30',
    iconColorClass: 'text-blue-600 dark:text-blue-400',
    label: '令牌刷新',
    value: (batch) => batch.token_refreshed_count,
    valueClass: 'text-2xl font-bold text-blue-600 dark:text-blue-400',
  },
  {
    icon: AlertTriangle,
    iconBgClass: 'bg-amber-100 dark:bg-amber-900/30',
    iconColorClass: 'text-amber-600 dark:text-amber-400',
    label: 'Session过期',
    value: (batch) => batch.session_expired_count,
    valueClass: 'text-2xl font-bold text-amber-600 dark:text-amber-400',
  },
  {
    icon: XCircle,
    iconBgClass: 'bg-red-100 dark:bg-red-900/30',
    iconColorClass: 'text-red-600 dark:text-red-400',
    label: '失败',
    value: (batch) => batch.failed_count,
    valueClass: 'text-2xl font-bold text-red-600 dark:text-red-400',
  },
  {
    icon: Clock,
    iconBgClass: 'bg-slate-100 dark:bg-slate-900/30',
    iconColorClass: 'text-slate-600 dark:text-slate-400',
    label: '健康率',
    value: (batch) =>
      `${
        batch.total_accounts > 0
          ? (
              ((batch.success_count + batch.token_refreshed_count) /
                batch.total_accounts) *
              100
            ).toFixed(1)
          : 0
      }%`,
    valueClass: 'text-2xl font-bold text-slate-600 dark:text-slate-400',
  },
]

const STATUS_INFO_MAP: Record<string, BatchLogStatusInfo> = {
  success: {
    label: '正常',
    color: 'text-green-600 dark:text-green-400',
    Icon: CheckCircle,
  },
  token_refreshed: {
    label: '令牌刷新',
    color: 'text-blue-600 dark:text-blue-400',
    Icon: Key,
  },
  session_expired: {
    label: 'Session过期',
    color: 'text-amber-600 dark:text-amber-400',
    Icon: AlertTriangle,
  },
  failed: {
    label: '失败',
    color: 'text-red-600 dark:text-red-400',
    Icon: XCircle,
  },
}

const columns: BatchLogTableColumn<LoginRenewLog>[] = [
  { title: '账号ID', render: (log) => renderAccountIdCell(log.account_id) },
  {
    title: '状态',
    render: (log) =>
      renderStatusBadge(
        STATUS_INFO_MAP[log.status] ?? {
          label: log.status,
          color: 'text-slate-500',
          Icon: Clock,
        },
      ),
  },
  { title: '说明', render: (log) => renderDescriptionCell(log.error_message, 60) },
  { title: '执行时间', render: (log) => renderDateTimeText(log.created_at) },
]

export function LoginRenewBatchDetailPage() {
  return (
    <BatchLogDetail<LoginRenewBatchDetail, LoginRenewLog>
      fetchDetail={getLoginRenewBatchDetail}
      backPath="/admin/login-renew-batches"
      summaryCards={summaryCards}
      summaryGridClass="grid-cols-2 md:grid-cols-3 lg:grid-cols-6"
      logTitle="续期日志"
      statusOptions={[
        { value: 'all', label: '全部状态' },
        { value: 'success', label: '正常' },
        { value: 'token_refreshed', label: '令牌刷新' },
        { value: 'session_expired', label: 'Session过期' },
        { value: 'failed', label: '失败' },
      ]}
      columns={columns}
      cardHeightStyle={{ height: 'calc(100vh - 420px)', minHeight: '300px' }}
    />
  )
}
