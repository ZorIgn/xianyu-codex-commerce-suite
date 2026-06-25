/**
 * 补发货批次详情页面
 *
 * 功能：
 * 1. 显示批次汇总信息
 * 2. 显示该批次所有订单发货日志列表
 * 3. 支持按状态筛选
 */
import { CheckCircle, Clock, Package, XCircle } from 'lucide-react'
import {
  getRedeliveryBatchDetail,
  type RedeliveryBatchDetail,
  type RedeliveryLog,
} from '@/api/redeliveryLogs'
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

const summaryCards: BatchLogSummaryCard<RedeliveryBatchDetail>[] = [
  {
    icon: Package,
    iconBgClass: 'bg-blue-100 dark:bg-blue-900/30',
    iconColorClass: 'text-blue-600 dark:text-blue-400',
    label: '处理订单数',
    value: (batch) => batch.total_orders,
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
        batch.total_orders > 0
          ? ((batch.success_count / batch.total_orders) * 100).toFixed(1)
          : 0
      }%`,
    valueClass: 'text-2xl font-bold text-amber-600 dark:text-amber-400',
  },
]

const columns: BatchLogTableColumn<RedeliveryLog>[] = [
  { title: '账号ID', render: (log) => renderAccountIdCell(log.account_id) },
  { title: '订单号', render: (log) => renderMonoCell(log.order_no) },
  { title: '状态', render: (log) => renderSuccessFailedBadge(log.status) },
  { title: '错误信息', render: (log) => renderTruncatedError(log.error_message, 50) },
  { title: '执行时间', render: (log) => renderDateTimeText(log.created_at) },
]

export function RedeliveryBatchDetailPage() {
  return (
    <BatchLogDetail<RedeliveryBatchDetail, RedeliveryLog>
      fetchDetail={getRedeliveryBatchDetail}
      backPath="/admin/redelivery-batches"
      summaryCards={summaryCards}
      logTitle="发货日志"
      statusOptions={[
        { value: 'all', label: '全部状态' },
        { value: 'success', label: '成功' },
        { value: 'failed', label: '失败' },
      ]}
      columns={columns}
    />
  )
}
