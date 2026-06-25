/**
 * 账号消息通知关闭日志批次详情页面
 *
 * 功能：
 * 1. 显示批次汇总信息（处理账号 / 关闭成功 / 关闭失败 / 执行时间）
 * 2. 显示该批次所有账号的关闭结果日志列表
 * 3. 支持按状态筛选（按钮组样式）
 */
import { CheckCircle, Clock, Users, XCircle } from 'lucide-react'
import {
  getCloseNoticeBatchDetail,
  type CloseNoticeBatchDetail,
  type CloseNoticeLog,
} from '@/api/closeNoticeLogs'
import {
  BatchLogDetail,
  renderDateTimeText,
  renderFullError,
  renderMonoCell,
  renderSuccessFailedBadge,
  type BatchLogSummaryCard,
  type BatchLogTableColumn,
} from '@/components/common/BatchLogDetail'
import { formatDateTime } from '@/utils/date'

const summaryCards: BatchLogSummaryCard<CloseNoticeBatchDetail>[] = [
  {
    icon: Users,
    iconColorClass: 'text-blue-500',
    label: '处理账号',
    value: (batch) => batch.total_accounts,
  },
  {
    icon: CheckCircle,
    iconColorClass: 'text-green-500',
    label: '关闭成功',
    value: (batch) => batch.success_count,
    valueClass: 'text-2xl font-bold text-green-600 dark:text-green-400',
  },
  {
    icon: XCircle,
    iconColorClass: 'text-red-500',
    label: '关闭失败',
    value: (batch) => batch.failed_count,
    valueClass: 'text-2xl font-bold text-red-600 dark:text-red-400',
  },
  {
    icon: Clock,
    iconColorClass: 'text-slate-400',
    label: '执行时间',
    value: (batch) => formatDateTime(batch.executed_at),
    valueClass: 'text-sm font-medium text-slate-700 dark:text-slate-300',
  },
]

const columns: BatchLogTableColumn<CloseNoticeLog>[] = [
  { title: '账号ID', render: (log) => renderMonoCell(log.account_id) },
  { title: '状态', render: (log) => renderSuccessFailedBadge(log.status) },
  { title: '错误信息', render: (log) => renderFullError(log.error_message) },
  { title: '记录时间', render: (log) => renderDateTimeText(log.created_at) },
]

export function CloseNoticeBatchDetailPage() {
  return (
    <BatchLogDetail<CloseNoticeBatchDetail, CloseNoticeLog>
      fetchDetail={getCloseNoticeBatchDetail}
      backPath="/admin/close-notice-batches"
      pageDescription={() => '消息通知关闭任务执行详细日志'}
      headerLayout="right-back"
      summaryCards={summaryCards}
      summaryGridClass="grid-cols-2 sm:grid-cols-4"
      summaryCardLayout="centered"
      logTitle="账号日志"
      filterStyle="pill"
      statusOptions={[
        { value: 'all', label: '全部' },
        { value: 'success', label: '成功' },
        { value: 'failed', label: '失败' },
      ]}
      columns={columns}
      cardHeightStyle={{ height: 'calc(100vh - 380px)', minHeight: '350px' }}
    />
  )
}
