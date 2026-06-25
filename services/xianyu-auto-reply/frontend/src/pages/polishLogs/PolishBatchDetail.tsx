/**
 * 擦亮批次详情页面
 *
 * 功能：
 * 1. 显示批次汇总信息
 * 2. 显示该批次所有商品擦亮日志列表
 * 3. 支持按状态筛选
 */
import { CheckCircle, Clock, Sparkles, XCircle } from 'lucide-react'
import { getPolishBatchDetail, type PolishBatchDetail, type PolishLog } from '@/api/polishLogs'
import {
  BatchLogDetail,
  renderAccountIdCell,
  renderDateTimeText,
  renderMonoCell,
  renderSuccessFailedBadge,
  renderTruncatedError,
  type BatchLogSummaryCard,
  type BatchLogTableColumn,
} from '@/components/common/BatchLogDetail'

const summaryCards: BatchLogSummaryCard<PolishBatchDetail>[] = [
  {
    icon: Sparkles,
    iconBgClass: 'bg-purple-100 dark:bg-purple-900/30',
    iconColorClass: 'text-purple-600 dark:text-purple-400',
    label: '处理商品数',
    value: (batch) => batch.total_items,
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
  {
    icon: Clock,
    iconBgClass: 'bg-amber-100 dark:bg-amber-900/30',
    iconColorClass: 'text-amber-600 dark:text-amber-400',
    label: '成功率',
    value: (batch) =>
      `${
        batch.total_items > 0
          ? ((batch.success_count / batch.total_items) * 100).toFixed(1)
          : 0
      }%`,
    valueClass: 'text-2xl font-bold text-amber-600 dark:text-amber-400',
  },
]

const columns: BatchLogTableColumn<PolishLog>[] = [
  { title: '账号ID', render: (log) => renderAccountIdCell(log.account_id) },
  { title: '商品ID', render: (log) => renderMonoCell(log.item_id) },
  { title: '状态', render: (log) => renderSuccessFailedBadge(log.status) },
  { title: '错误信息', render: (log) => renderTruncatedError(log.error_message, 50) },
  { title: '执行时间', render: (log) => renderDateTimeText(log.created_at) },
]

export function PolishBatchDetailPage() {
  return (
    <BatchLogDetail<PolishBatchDetail, PolishLog>
      fetchDetail={getPolishBatchDetail}
      backPath="/admin/polish-batches"
      summaryCards={summaryCards}
      logTitle="擦亮日志"
      statusOptions={[
        { value: 'all', label: '全部状态' },
        { value: 'success', label: '成功' },
        { value: 'failed', label: '失败' },
      ]}
      columns={columns}
    />
  )
}
