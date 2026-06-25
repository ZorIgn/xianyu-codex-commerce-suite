/**
 * COOKIES刷新批次列表页面
 *
 * 功能：
 * 1. 显示COOKIES刷新批次列表
 * 2. 支持按日期范围筛选和分页查看
 */
import { Clock } from 'lucide-react'
import { getCookiesRefreshBatches, type CookiesRefreshBatch } from '@/api/cookiesRefreshLogs'
import {
  BatchLogList,
  renderFailedCount,
  renderIconCount,
  renderPlainCount,
  renderSuccessCount,
  type BatchLogColumn,
} from '@/components/common/BatchLogList'

const columns: BatchLogColumn<CookiesRefreshBatch>[] = [
  {
    title: '处理账号数',
    render: (batch) => renderPlainCount(batch.total_accounts),
  },
  {
    title: '初始化',
    render: (batch) => renderIconCount(batch.initialized_count, Clock, 'text-amber-600 dark:text-amber-400'),
  },
  {
    title: '成功',
    render: (batch) => renderSuccessCount(batch.success_count),
  },
  {
    title: '失败',
    render: (batch) => renderFailedCount(batch.failed_count),
  },
]

export function CookiesRefreshBatches() {
  return (
    <BatchLogList
      title="COOKIES刷新日志"
      description="查看独立 COOKIES 续期任务的执行记录"
      fetchBatches={getCookiesRefreshBatches}
      columns={columns}
      detailPath={(batchId) => `/admin/cookies-refresh-batches/${batchId}`}
      loadErrorMessage="加载COOKIES刷新日志失败"
    />
  )
}
